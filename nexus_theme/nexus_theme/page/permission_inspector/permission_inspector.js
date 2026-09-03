// Permission Inspector — /app/permission-inspector
//
// A window onto Frappe's own role-permission records for one User or one
// Role. The backend (nexus_theme/permission_inspector/api.py) reads through
// Frappe's permission helpers and writes through Custom DocPerm, exactly as
// the stock Role Permission Manager does. This file only draws, filters and
// batches edits; the numbers it shows are Frappe's, not its own.
//
// Loaded by Frappe's Page loader together with the .html and .css beside it.

/* global nexus_theme */
frappe.provide("nexus_theme.permission_inspector");

frappe.pages["permission-inspector"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Permission Inspector"),
		single_column: true,
	});
	wrapper.inspector = new nexus_theme.permission_inspector.Inspector(wrapper, page);
};

frappe.pages["permission-inspector"].on_page_show = function (wrapper) {
	if (wrapper.inspector) {
		wrapper.inspector.apply_route_options();
	}
};

(function () {
	"use strict";

	const API = "nexus_theme.permission_inspector.api";
	const esc = (v) => frappe.utils.escape_html(v == null ? "" : String(v));
	const GLYPH = { 1: "✓", 0: "✗", 2: "◐", na: "—" };
	const CHUNK = 150; // rows rendered per animation frame

	// Frappe's rule dependencies (frappe.core.doctype.doctype.validate_permissions).
	// Ticking a flag pulls in what it needs; clearing one drops what needed it.
	const NEEDS = { cancel: ["submit", "write"], submit: ["write"], amend: ["write"], import: ["create"] };
	const DEPENDENTS = { write: ["submit", "cancel", "amend"], submit: ["cancel"], create: ["import"] };

	const FLAG_LABELS = {
		single: __("Single"),
		submittable: __("Submittable"),
		tree: __("Tree"),
		virtual: __("Virtual"),
		custom: __("Custom"),
		child: __("Child table"),
	};

	class Inspector {
		constructor(wrapper, page) {
			this.wrapper = wrapper;
			this.page = page;
			this.$root = $(frappe.render_template("permission_inspector", {}));
			$(page.main).addClass("nxpi-page").empty().append(this.$root);

			this.options = null;
			this.target = null; // { type: "user"|"role", name }
			this.data = null; // last get_matrix response
			this.rows = [];
			this.row_index = new Map();
			this.pending = new Map(); // key -> { doctype, role, ptype, value }
			this.editing = false;
			this.filters = { search: "", module: "", ptype: "", show: "all", child: false };
			this.drawer_doctype = null;
			this.render_token = 0;
			this._silent = false;

			this.cache_dom();
			this.make_controls();
			this.bind();
			this.load_options();
		}

		// ------------------------------------------------------------------
		// Setup
		// ------------------------------------------------------------------

		cache_dom() {
			const $ = (sel) => this.$root.find(sel);
			this.$target_info = $(".nxpi-target-info");
			this.$toolbar = $(".nxpi-toolbar");
			this.$body = $(".nxpi-body");
			this.$empty = $(".nxpi-empty");
			this.$thead = $(".nxpi-table thead");
			this.$tbody = $(".nxpi-table tbody");
			this.$wrap = $(".nxpi-matrix-wrap");
			this.$no_rows = $(".nxpi-no-rows");
			this.$drawer = $(".nxpi-drawer");
			this.$userperms = $(".nxpi-userperms");
			this.$popover = $(".nxpi-popover");
			this.$count = $(".nxpi-count");
			this.$edit_btn = $(".nxpi-edit");
			this.$module = $(".nxpi-module");
			this.$ptype = $(".nxpi-ptype");
			this.$show = $(".nxpi-show");
			this.$search = $(".nxpi-search");
			this.$child = $(".nxpi-child");
		}

		make_controls() {
			this.user_control = frappe.ui.form.make_control({
				df: {
					fieldtype: "Link",
					options: "User",
					fieldname: "nxpi_user",
					placeholder: __("Pick a user"),
					get_query: () => ({
						filters: [
							["User", "name", "!=", "Guest"],
							["User", "user_type", "=", "System User"],
						],
					}),
					change: () => this.on_pick("user"),
				},
				parent: this.$root.find('[data-control="user"]'),
				render_input: true,
			});
			this.role_control = frappe.ui.form.make_control({
				df: {
					fieldtype: "Link",
					options: "Role",
					fieldname: "nxpi_role",
					placeholder: __("Pick a role"),
					get_query: () => ({ filters: { disabled: 0 } }),
					change: () => this.on_pick("role"),
				},
				parent: this.$root.find('[data-control="role"]'),
				render_input: true,
			});
			this.user_control.refresh();
			this.role_control.refresh();
		}

		bind() {
			this.$root.on("click", ".nxpi-clear", () => this.clear());

			const debounced = frappe.utils.debounce(() => {
				this.filters.search = (this.$search.val() || "").trim().toLowerCase();
				this.render_table();
			}, 150);
			this.$search.on("input", debounced);
			this.$module.on("change", () => {
				this.filters.module = this.$module.val();
				this.render_table();
			});
			this.$ptype.on("change", () => {
				this.filters.ptype = this.$ptype.val();
				this.render_table();
			});
			this.$show.on("change", () => {
				this.filters.show = this.$show.val();
				this.render_table();
			});
			this.$child.on("change", () => {
				this.filters.child = this.$child.prop("checked");
				this.reload();
			});
			this.$root.on("click", ".nxpi-refresh", () => this.refresh_from_server());
			this.$edit_btn.on("click", () => this.toggle_edit());

			// Matrix
			this.$tbody.on("click", ".nxpi-dt-link", (e) => {
				e.preventDefault();
				this.open_drawer($(e.currentTarget).data("dt"));
			});
			this.$tbody.on("click", ".nxpi-cell.is-editable", (e) => this.on_cell_click(e));
			this.$tbody.on("change", ".nxpi-cell input[type=checkbox]", (e) => this.on_role_checkbox(e));

			// Target info actions
			this.$root.on("click", ".nxpi-open-userperms", () => this.toggle_userperms());
			this.$root.on("click", ".nxpi-open-manager", () => frappe.set_route("permission-manager"));
			this.$root.on("click", ".nxpi-open-user", () => {
				if (this.target && this.target.type === "user") frappe.set_route("Form", "User", this.target.name);
			});
			this.$root.on("click", ".nxpi-open-role", () => {
				if (this.target && this.target.type === "role") frappe.set_route("Form", "Role", this.target.name);
			});

			// Drawer
			this.$drawer.on("click", ".nxpi-drawer-close", () => this.close_drawer());
			this.$drawer.on("click", ".nxpi-drawer-manager", () => {
				if (this.drawer_doctype) frappe.set_route("permission-manager", this.drawer_doctype);
			});
			this.$drawer.on("click", ".nxpi-drawer-up-list", () => {
				if (!this.target) return;
				frappe.route_options = { user: this.target.name, allow: this.drawer_doctype };
				frappe.set_route("List", "User Permission");
			});

			// User Permissions panel
			this.$userperms.on("click", ".nxpi-up-manage", () => {
				frappe.route_options = { user: this.target.name };
				frappe.set_route("List", "User Permission");
			});
			this.$userperms.on("click", ".nxpi-up-new", () => {
				frappe.new_doc("User Permission", { user: this.target.name });
			});
			this.$userperms.on("click", ".nxpi-up-close", () => this.$userperms.prop("hidden", true));

			// Popover
			this.$popover.on("change", "input[type=checkbox]", (e) => this.on_popover_checkbox(e));
			this.$popover.on("click", ".nxpi-popover-all", (e) => this.popover_set_all($(e.currentTarget).data("value")));
			this.$popover.on("click", ".nxpi-popover-close", () => this.close_popover());
			$(document).on("mousedown.nxpi", (e) => {
				if (this.$popover.prop("hidden")) return;
				if ($(e.target).closest(".nxpi-popover, .nxpi-cell").length) return;
				this.close_popover();
			});
			$(document).on("keydown.nxpi", (e) => {
				if (e.key === "Escape") {
					this.close_popover();
				}
			});
			this.$wrap.on("scroll", () => this.close_popover());

			$(window).on("beforeunload.nxpi", () => {
				if (this.pending.size) return __("You have unsaved permission changes.");
			});
		}

		load_options() {
			frappe.xcall(`${API}.get_options`).then((opts) => {
				this.options = opts;
				this.fill_ptype_select(opts.columns, []);
			});
		}

		apply_route_options() {
			const ro = frappe.route_options;
			if (!ro) return;
			const kind = ro.user ? "user" : ro.role ? "role" : null;
			if (!kind) return;
			frappe.route_options = null;
			const value = ro[kind];
			this.silently(() => {
				(kind === "user" ? this.user_control : this.role_control).set_value(value);
				(kind === "user" ? this.role_control : this.user_control).set_value("");
			});
			this.select(kind, value);
		}

		silently(fn) {
			this._silent = true;
			try {
				fn();
			} finally {
				setTimeout(() => (this._silent = false), 0);
			}
		}

		// ------------------------------------------------------------------
		// Target selection and loading
		// ------------------------------------------------------------------

		on_pick(kind) {
			if (this._silent) return;
			const control = kind === "user" ? this.user_control : this.role_control;
			const value = control.get_value();
			if (!value) {
				if (this.target && this.target.type === kind) this.clear();
				return;
			}
			const other = kind === "user" ? this.role_control : this.user_control;
			if (other.get_value()) this.silently(() => other.set_value(""));
			this.select(kind, value);
		}

		select(kind, name) {
			if (this.pending.size && !this.confirm_discard()) {
				return;
			}
			this.target = { type: kind, name };
			this.pending.clear();
			this.editing = false;
			this.close_drawer();
			this.$userperms.prop("hidden", true).empty();
			this.update_dirty();
			this.reload();
		}

		confirm_discard() {
			// Called synchronously from selection; we cannot await a dialog here,
			// so unsaved edits block the switch and say so.
			frappe.show_alert({
				message: __("Save or discard your unsaved permission changes first."),
				indicator: "orange",
			});
			return false;
		}

		clear() {
			if (this.pending.size) {
				this.confirm_discard();
				return;
			}
			this.silently(() => {
				this.user_control.set_value("");
				this.role_control.set_value("");
			});
			this.target = null;
			this.data = null;
			this.rows = [];
			this.row_index.clear();
			this.editing = false;
			this.close_drawer();
			this.close_popover();
			this.$userperms.prop("hidden", true).empty();
			this.$target_info.prop("hidden", true).empty();
			this.$toolbar.prop("hidden", true);
			this.$body.prop("hidden", true);
			this.$empty.prop("hidden", false);
			this.update_dirty();
		}

		reload() {
			if (!this.target) return;
			const token = ++this.render_token;
			frappe.dom.freeze(__("Reading permissions…"));
			frappe
				.xcall(`${API}.get_matrix`, {
					target_type: this.target.type,
					target: this.target.name,
					include_child: this.filters.child ? 1 : 0,
				})
				.then((data) => {
					if (token !== this.render_token) return;
					this.data = data;
					this.rows = data.rows || [];
					this.row_index = new Map(this.rows.map((r) => [r.n, r]));
					this.columns = data.columns || [];
					this.locked_roles = new Set(data.locked_roles || []);
					this.render_target_info();
					this.fill_module_select();
					this.fill_ptype_select(this.columns, this.custom_ptypes());
					this.$empty.prop("hidden", true);
					this.$toolbar.prop("hidden", false);
					this.$body.prop("hidden", false);
					this.update_edit_button();
					this.render_table();
					if (this.drawer_doctype && this.row_index.has(this.drawer_doctype)) {
						this.open_drawer(this.drawer_doctype);
					} else {
						this.close_drawer();
					}
				})
				.catch(() => {
					this.$toolbar.prop("hidden", true);
					this.$body.prop("hidden", true);
					this.$empty.prop("hidden", false);
				})
				.finally(() => frappe.dom.unfreeze());
		}

		refresh_from_server() {
			if (!this.target) return;
			if (this.pending.size) {
				this.confirm_discard();
				return;
			}
			frappe
				.xcall(`${API}.refresh_cache`, { target_type: this.target.type, target: this.target.name })
				.then(() => {
					frappe.show_alert({ message: __("Permission caches cleared."), indicator: "blue" });
					this.reload();
				});
		}

		custom_ptypes() {
			const set = new Set();
			this.rows.forEach((r) => (r.x || []).forEach((x) => set.add(x)));
			return Array.from(set).sort();
		}

		// ------------------------------------------------------------------
		// Target summary
		// ------------------------------------------------------------------

		render_target_info() {
			const t = this.data.target;
			const stats = this.stats();
			let html = "";

			if (t.type === "user") {
				const badges = [];
				badges.push(
					t.enabled
						? `<span class="indicator-pill green">${__("Enabled")}</span>`
						: `<span class="indicator-pill red">${__("Disabled")}</span>`
				);
				badges.push(`<span class="indicator-pill gray">${esc(t.user_type)}</span>`);
				if (t.is_system_manager && !t.is_admin) {
					badges.push(`<span class="indicator-pill blue">${__("System Manager")}</span>`);
				}
				const chips = t.roles
					.map((r) => {
						const cls = ["nxpi-chip"];
						if (t.disabled_roles.includes(r)) cls.push("is-disabled");
						if (this.locked_roles.has(r)) cls.push("is-locked");
						const title = t.disabled_roles.includes(r)
							? __("This role is disabled")
							: this.locked_roles.has(r)
							? __("This role's rules cannot be edited here")
							: "";
						return `<span class="${cls.join(" ")}" title="${esc(title)}">${esc(r)}</span>`;
					})
					.concat(
						t.automatic_roles.map(
							(r) =>
								`<span class="nxpi-chip is-auto" title="${esc(__("Automatic role: every user of this type has it"))}">${esc(r)}</span>`
						)
					)
					.join("");

				let notes = "";
				if (t.is_admin) {
					notes += `<div class="nxpi-note is-warn">${__(
						"Administrator bypasses role permissions entirely. Every DocType is fully allowed and nothing on this screen can change that."
					)}</div>`;
				} else if (!t.roles.length) {
					notes += `<div class="nxpi-note is-warn">${__("This user has no roles, so no role grants them anything.")}</div>`;
				}
				if (!t.enabled) {
					notes += `<div class="nxpi-note is-warn">${__("Disabled users cannot log in. The permissions below are what they would get if enabled.")}</div>`;
				}
				if (t.blocked_modules && t.blocked_modules.length) {
					notes += `<div class="nxpi-note">${__("Blocked modules on the User record: {0}", [
						esc(t.blocked_modules.join(", ")),
					])}</div>`;
				}

				html = `
					<div class="nxpi-info-main">
						<div class="nxpi-info-title">${esc(t.label)} <span class="nxpi-info-sub">${esc(t.name)}</span> ${badges.join(" ")}</div>
						<div class="nxpi-info-sub">${__("Last login")}: ${t.last_login ? esc(frappe.datetime.prettyDate(t.last_login)) : __("never")}</div>
						<div class="nxpi-chips">${chips || `<span class="nxpi-info-sub">${__("No roles")}</span>`}</div>
						${notes}
					</div>
					${this.stats_html(stats)}
					<div class="nxpi-info-actions">
						<button class="btn btn-default btn-xs nxpi-open-userperms">${__("User Permissions")} (${t.user_permission_count})</button>
						<button class="btn btn-default btn-xs nxpi-open-user">${__("Open User")}</button>
						<button class="btn btn-default btn-xs nxpi-open-manager">${__("Role Permission Manager")}</button>
					</div>`;
			} else {
				const badges = [];
				badges.push(
					t.disabled
						? `<span class="indicator-pill red">${__("Disabled")}</span>`
						: `<span class="indicator-pill green">${__("Active")}</span>`
				);
				if (t.desk_access) badges.push(`<span class="indicator-pill gray">${__("Desk access")}</span>`);
				if (t.is_custom) badges.push(`<span class="indicator-pill gray">${__("Custom role")}</span>`);
				if (t.is_automatic) badges.push(`<span class="indicator-pill blue">${__("Automatic")}</span>`);
				if (t.two_factor_auth) badges.push(`<span class="indicator-pill orange">${__("2FA")}</span>`);

				let notes = "";
				if (this.locked_roles.has(t.name)) {
					notes += `<div class="nxpi-note is-warn">${__("The rules of this role cannot be edited from here.")}</div>`;
				}
				if (t.name === "System Manager") {
					notes += `<div class="nxpi-note">${__(
						"System Managers can also import and export any DocType and manage permissions, on top of the rules below."
					)}</div>`;
				}
				const users = t.users.length
					? esc(t.users.slice(0, 12).join(", ")) + (t.user_count > 12 ? ` +${t.user_count - 12}` : "")
					: __("nobody");

				html = `
					<div class="nxpi-info-main">
						<div class="nxpi-info-title">${esc(t.label)} ${badges.join(" ")}</div>
						<div class="nxpi-info-sub" title="${users}">${__("Held by {0} enabled user(s)", [t.user_count])}: ${users}</div>
						${notes}
					</div>
					${this.stats_html(stats)}
					<div class="nxpi-info-actions">
						<button class="btn btn-default btn-xs nxpi-open-role">${__("Open Role")}</button>
						<button class="btn btn-default btn-xs nxpi-open-manager">${__("Role Permission Manager")}</button>
					</div>`;
			}
			this.$target_info.html(html).prop("hidden", false);
		}

		stats() {
			const keys = ["read", "write", "create", "submit", "delete"];
			const out = { total: this.rows.length };
			keys.forEach((k) => (out[k] = 0));
			this.rows.forEach((row) => {
				const p = this.effective(row).perms;
				keys.forEach((k) => {
					if (p[k]) out[k] += 1;
				});
			});
			return out;
		}

		stats_html(s) {
			const tile = (n, label) => `<div class="nxpi-stat"><b>${n}</b><span>${label}</span></div>`;
			return `<div class="nxpi-stats">
				${tile(s.total, __("DocTypes"))}
				${tile(s.read, __("Read"))}
				${tile(s.write, __("Write"))}
				${tile(s.create, __("Create"))}
				${tile(s.submit, __("Submit"))}
				${tile(s.delete, __("Delete"))}
			</div>`;
		}

		refresh_stats() {
			this.$target_info.find(".nxpi-stats").replaceWith(this.stats_html(this.stats()));
		}

		// ------------------------------------------------------------------
		// Filters
		// ------------------------------------------------------------------

		fill_module_select() {
			const current = this.filters.module;
			const modules = Array.from(new Set(this.rows.map((r) => r.m))).sort((a, b) => a.localeCompare(b));
			this.$module.empty().append(`<option value="">${__("All modules")}</option>`);
			modules.forEach((m) => this.$module.append(`<option value="${esc(m)}">${esc(m)}</option>`));
			if (modules.includes(current)) this.$module.val(current);
			else this.filters.module = "";
		}

		fill_ptype_select(columns, extra) {
			const current = this.filters.ptype;
			this.$ptype.empty().append(`<option value="">${__("Any permission")}</option>`);
			columns.forEach((c) => this.$ptype.append(`<option value="${esc(c.key)}">${esc(c.label)}</option>`));
			extra.forEach((x) => this.$ptype.append(`<option value="${esc(x)}">${esc(frappe.unscrub(x))}</option>`));
			const valid = columns.some((c) => c.key === current) || extra.includes(current);
			if (valid) this.$ptype.val(current);
			else this.filters.ptype = "";
		}

		visible_rows() {
			const f = this.filters;
			const rights = this.data.rights;
			return this.rows.filter((row) => {
				if (f.search && !(row.n.toLowerCase().includes(f.search) || row.m.toLowerCase().includes(f.search))) {
					return false;
				}
				if (f.module && row.m !== f.module) return false;
				if (f.show === "customised") return !!row.c;
				if (f.show === "changed") return this.row_has_pending(row.n);
				if (f.show === "all") return true;

				const p = this.effective(row).perms;
				const keys = f.ptype ? [f.ptype] : rights.concat(row.x || []);
				if (f.ptype && (row.na || []).includes(f.ptype)) return false;
				const any_on = keys.some((k) => p[k]);
				return f.show === "enabled" ? any_on : !any_on;
			});
		}

		// ------------------------------------------------------------------
		// Effective permission maths (mirrors api._evaluate)
		// ------------------------------------------------------------------

		scope_roles() {
			const t = this.data.target;
			if (t.type === "role") return [t.name];
			return (t.roles || []).concat(t.automatic_roles || []);
		}

		all_rights(row) {
			return this.data.rights.concat(row.x || []);
		}

		base_grants(row, role) {
			return new Set((row.r && row.r[role]) || []);
		}

		pending_key(doctype, role, ptype) {
			return `${doctype} ${role} ${ptype}`;
		}

		pending_value(doctype, role, ptype) {
			const ch = this.pending.get(this.pending_key(doctype, role, ptype));
			return ch ? ch.value : null;
		}

		row_has_pending(doctype) {
			for (const ch of this.pending.values()) {
				if (ch.doctype === doctype) return true;
			}
			return false;
		}

		// Current (base + pending) plain-rule grants of one role on one row.
		role_grants(row, role) {
			const set = this.base_grants(row, role);
			this.all_rights(row).forEach((pt) => {
				const v = this.pending_value(row.n, role, pt);
				if (v === 1) set.add(pt);
				else if (v === 0) set.delete(pt);
			});
			return set;
		}

		effective(row) {
			if (!this.row_has_pending(row.n)) {
				return { perms: row.p || {}, sources: row.s || null };
			}
			const rights = this.all_rights(row);
			const na = new Set(row.na || []);
			const rules = [];
			this.scope_roles().forEach((role) => {
				const grants = this.role_grants(row, role);
				if (grants.size || (row.r && row.r[role])) rules.push({ role, if_owner: 0, grants });
				if (row.o && row.o[role]) rules.push({ role, if_owner: 1, grants: new Set(row.o[role]) });
			});
			const has_owner = rules.some((r) => r.if_owner);
			const perms = {};
			const sources = {};
			rights.forEach((pt) => {
				if (na.has(pt)) return;
				const granting = rules.filter((r) => r.grants.has(pt));
				if (!granting.length) return;
				const outright = granting.filter((r) => !r.if_owner);
				perms[pt] = has_owner && !outright.length && pt !== "create" ? 2 : 1;
				sources[pt] = outright
					.map((r) => r.role)
					.sort()
					.concat(
						granting
							.filter((r) => r.if_owner)
							.map((r) => `${r.role} (${__("if owner")})`)
							.sort()
					);
			});
			if (!perms.select && rights.includes("select") && perms.read) {
				perms.select = perms.read;
				sources.select = [__("implied by Read")].concat(sources.read || []);
			}
			return { perms, sources: this.data.target.type === "user" ? sources : null };
		}

		// ------------------------------------------------------------------
		// Matrix rendering
		// ------------------------------------------------------------------

		has_custom_column() {
			return this.rows.some((r) => r.x && r.x.length);
		}

		render_head() {
			const focus = this.filters.ptype;
			let html = `<tr><th class="nxpi-h-dt">${__("DocType")}</th><th class="nxpi-h-mod">${__("Module")}</th>`;
			this.columns.forEach((c) => {
				html += `<th class="nxpi-h-col${c.key === focus ? " is-focus" : ""}" title="${esc(c.description)}">${esc(c.label)}</th>`;
			});
			if (this.has_custom_column()) {
				html += `<th title="${esc(__("Custom permission types defined for this DocType"))}">${__("Custom")}</th>`;
			}
			html += `<th class="nxpi-h-src">${this.data.target.type === "user" ? __("Granted by") : __("Source")}</th></tr>`;
			this.$thead.html(html);
		}

		render_table() {
			if (!this.data) return;
			this.close_popover();
			this.render_head();
			const visible = this.visible_rows();
			this.$count.text(__("{0} of {1} DocTypes", [visible.length, this.rows.length]));
			this.$no_rows.prop("hidden", visible.length > 0);
			this.$tbody.empty();

			const token = ++this.render_token;
			const with_custom = this.has_custom_column();
			let i = 0;
			const step = () => {
				if (token !== this.render_token) return;
				const parts = [];
				const end = Math.min(i + CHUNK, visible.length);
				for (; i < end; i++) parts.push(this.row_html(visible[i], with_custom));
				this.$tbody[0].insertAdjacentHTML("beforeend", parts.join(""));
				if (i < visible.length) window.requestAnimationFrame(step);
			};
			step();
		}

		rerender_row(doctype) {
			const row = this.row_index.get(doctype);
			if (!row) return;
			const $old = this.$tbody.find(`tr[data-dt="${CSS.escape(doctype)}"]`);
			if (!$old.length) return;
			$old.replaceWith(this.row_html(row, this.has_custom_column()));
		}

		row_html(row, with_custom) {
			const ev = this.effective(row);
			const changed = this.row_has_pending(row.n);
			const flags = Object.keys(FLAG_LABELS)
				.filter((k) => row.f && row.f[k])
				.map((k) => `<span class="nxpi-flag">${FLAG_LABELS[k]}</span>`)
				.join("");
			const customised = row.c
				? `<span class="nxpi-flag is-customised" title="${esc(__("Rules differ from the standard shipped in code"))}">${__("Customised")}</span>`
				: "";
			const lock = row.lock ? ` title="${esc(row.lock)}"` : "";

			let tds = `<td class="nxpi-dt"${lock}><a href="#" class="nxpi-dt-link" data-dt="${esc(row.n)}">${esc(row.n)}</a>${customised}${flags}</td>`;
			tds += `<td class="nxpi-mod" title="${esc(row.m)}">${esc(row.m)}</td>`;
			this.columns.forEach((c) => {
				tds += this.cell_html(row, c.key, c.label, ev);
			});
			if (with_custom) {
				tds += `<td class="nxpi-xcell">${(row.x || [])
					.map((x) => this.custom_chip_html(row, x, ev))
					.join("")}</td>`;
			}
			tds += `<td class="nxpi-src">${this.source_html(row, ev)}</td>`;
			const cls = ["nxpi-row"];
			if (changed) cls.push("is-changed");
			if (row.lock) cls.push("is-locked");
			return `<tr class="${cls.join(" ")}" data-dt="${esc(row.n)}">${tds}</tr>`;
		}

		cell_state(row, ptype, ev) {
			if ((row.na || []).includes(ptype)) return "na";
			return ev.perms[ptype] || 0;
		}

		cell_title(row, ptype, label, state, ev) {
			const status =
				state === "na"
					? __("Not applicable to this DocType")
					: state === 2
					? __("Only for documents the user owns")
					: state === 1
					? __("Allowed")
					: __("Not allowed");
			let text = `${label}: ${status}`;
			if (state !== "na" && state !== 0) {
				if (this.data.target.type === "user") {
					const src = (ev.sources && ev.sources[ptype]) || [];
					if (src.length) text += `\n${__("Granted by")}: ${src.join(", ")}`;
				} else {
					text += `\n${__("Source")}: ${__("Current role")}`;
					if (row.o && row.o[this.data.target.name] && row.o[this.data.target.name].includes(ptype)) {
						text += ` (${__("if owner")})`;
					}
				}
			}
			if (row.lock) text += `\n${row.lock}`;
			return text;
		}

		is_cell_editable(row, ptype) {
			if (!this.editing || row.lock) return false;
			if ((row.na || []).includes(ptype)) return false;
			const t = this.data.target;
			if (t.type === "user") return !t.is_admin;
			return !this.locked_roles.has(t.name);
		}

		cell_html(row, ptype, label, ev) {
			const state = this.cell_state(row, ptype, ev);
			const editable = this.is_cell_editable(row, ptype);
			const cls = ["nxpi-cell", `is-${state}`];
			if (editable) cls.push("is-editable");
			if (ptype === this.filters.ptype) cls.push("is-focus");
			const pending = this.scope_roles().some((role) => this.pending_value(row.n, role, ptype) !== null);
			if (pending) cls.push("is-pending");
			const title = esc(this.cell_title(row, ptype, label, state, ev));

			let inner;
			if (editable && this.data.target.type === "role") {
				const role = this.data.target.name;
				const checked = this.role_grants(row, role).has(ptype) ? " checked" : "";
				const owner_mark =
					row.o && row.o[role] && row.o[role].includes(ptype)
						? `<span class="nxpi-owner-mark" title="${esc(__("Also granted by an if-owner rule"))}">${GLYPH[2]}</span>`
						: "";
				inner = `<input type="checkbox" data-role="${esc(role)}"${checked}>${owner_mark}`;
			} else {
				inner = GLYPH[state];
			}
			return `<td class="${cls.join(" ")}" data-dt="${esc(row.n)}" data-pt="${esc(ptype)}" data-label="${esc(label)}" title="${title}">${inner}</td>`;
		}

		custom_chip_html(row, ptype, ev) {
			const state = this.cell_state(row, ptype, ev);
			const editable = this.is_cell_editable(row, ptype);
			const label = frappe.unscrub(ptype);
			const cls = ["nxpi-xchip", "nxpi-cell", `is-${state}`];
			if (editable) cls.push("is-editable");
			const pending = this.scope_roles().some((role) => this.pending_value(row.n, role, ptype) !== null);
			if (pending) cls.push("is-pending");
			const title = esc(this.cell_title(row, ptype, label, state, ev));
			let mark = GLYPH[state];
			if (editable && this.data.target.type === "role") {
				const checked = this.role_grants(row, this.data.target.name).has(ptype) ? " checked" : "";
				mark = `<input type="checkbox" data-role="${esc(this.data.target.name)}"${checked}>`;
			}
			return `<span class="${cls.join(" ")}" data-dt="${esc(row.n)}" data-pt="${esc(ptype)}" data-label="${esc(label)}" title="${title}">${esc(label)} ${mark}</span>`;
		}

		source_html(row, ev) {
			if (this.data.target.type === "role") {
				const role = this.data.target.name;
				const bits = [];
				if (row.r && row.r[role]) bits.push(__("Current role"));
				if (row.o && row.o[role]) bits.push(`<span class="nxpi-chip">${__("if owner")}</span>`);
				if (row.lr && row.lr.length) bits.push(`<span class="nxpi-chip is-locked">${__("locked")}</span>`);
				return bits.join(" ") || (Object.keys(ev.perms).length ? "" : `<span>${__("No rule")}</span>`);
			}
			if (this.data.target.is_admin) return __("Administrator");
			const roles = new Set();
			Object.keys(ev.sources || {}).forEach((pt) => {
				(ev.sources[pt] || []).forEach((s) => {
					if (s !== __("implied by Read")) roles.add(s);
				});
			});
			const list = Array.from(roles).sort();
			if (!list.length) return `<span>${__("No rule")}</span>`;
			const shown = list.slice(0, 3).map((r) => `<span class="nxpi-chip" title="${esc(r)}">${esc(r)}</span>`);
			if (list.length > 3) shown.push(`<span class="nxpi-chip" title="${esc(list.slice(3).join(", "))}">+${list.length - 3}</span>`);
			return shown.join(" ");
		}

		// ------------------------------------------------------------------
		// Editing
		// ------------------------------------------------------------------

		update_edit_button() {
			const t = this.data.target;
			const blocked = t.type === "user" ? t.is_admin : this.locked_roles.has(t.name);
			this.$edit_btn
				.prop("disabled", blocked)
				.toggleClass("is-on", this.editing)
				.text(this.editing ? __("Done editing") : __("Edit permissions"))
				.attr(
					"title",
					blocked
						? t.type === "user"
							? __("Administrator's access cannot be edited")
							: __("This role's rules cannot be edited here")
						: this.editing
						? __("Leave edit mode; unsaved changes stay pending")
						: __("Change the underlying role permissions from this screen")
				);
		}

		toggle_edit() {
			if (!this.data) return;
			this.editing = !this.editing;
			this.update_edit_button();
			this.render_table();
			if (this.editing && this.data.target.type === "user") {
				frappe.show_alert({
					message: __("Click a cell to choose which of the user's roles should change."),
					indicator: "blue",
				});
			}
		}

		set_pending(doctype, role, ptype, value, cascade = true) {
			const row = this.row_index.get(doctype);
			if (!row) return;
			if ((row.na || []).includes(ptype)) return;
			const base = this.base_grants(row, role).has(ptype) ? 1 : 0;
			const key = this.pending_key(doctype, role, ptype);
			if (value === base) this.pending.delete(key);
			else this.pending.set(key, { doctype, role, ptype, value });

			if (cascade) {
				const linked = value ? NEEDS[ptype] || [] : DEPENDENTS[ptype] || [];
				linked.forEach((other) => {
					if (this.role_grants(row, role).has(other) !== !!value) {
						this.set_pending(doctype, role, other, value, true);
					}
				});
			}
		}

		on_role_checkbox(e) {
			const $input = $(e.currentTarget);
			const $cell = $input.closest(".nxpi-cell");
			const doctype = $cell.data("dt");
			const ptype = $cell.data("pt");
			const role = $input.data("role");
			this.set_pending(doctype, role, ptype, $input.prop("checked") ? 1 : 0);
			this.after_edit(doctype);
		}

		on_cell_click(e) {
			if ($(e.target).is("input")) return; // the checkbox handles itself
			const $cell = $(e.currentTarget);
			const doctype = $cell.data("dt");
			const ptype = $cell.data("pt");
			if (this.data.target.type === "role") {
				const $input = $cell.find("input[type=checkbox]");
				if ($input.length) $input.prop("checked", !$input.prop("checked")).trigger("change");
				return;
			}
			this.open_popover($cell, doctype, ptype, $cell.data("label"));
		}

		after_edit(doctype) {
			this.rerender_row(doctype);
			this.update_dirty();
			this.refresh_stats();
		}

		update_dirty() {
			const n = this.pending.size;
			if (n) {
				this.page.set_indicator(__("{0} unsaved", [n]), "orange");
				this.page.set_primary_action(__("Save Changes"), () => this.save(), "save");
				this.page.set_secondary_action(__("Discard"), () => this.discard());
			} else {
				this.page.clear_indicator();
				this.page.clear_primary_action();
				this.page.clear_secondary_action();
			}
		}

		discard() {
			if (!this.pending.size) return;
			const touched = Array.from(new Set(Array.from(this.pending.values()).map((c) => c.doctype)));
			this.pending.clear();
			this.close_popover();
			this.update_dirty();
			if (this.filters.show === "changed") this.render_table();
			else touched.forEach((dt) => this.rerender_row(dt));
			this.refresh_stats();
			frappe.show_alert({ message: __("Changes discarded."), indicator: "blue" });
		}

		save() {
			if (!this.pending.size || !this.target) return;
			const changes = Array.from(this.pending.values());
			this.close_popover();
			frappe.dom.freeze(__("Saving {0} permission change(s)…", [changes.length]));
			frappe
				.xcall(`${API}.save_changes`, {
					changes,
					target_type: this.target.type,
					target: this.target.name,
					include_child: this.filters.child ? 1 : 0,
				})
				.then((r) => {
					const touched = r.doctypes || [];
					(r.rows || []).forEach((fresh) => {
						this.row_index.set(fresh.n, fresh);
						const i = this.rows.findIndex((x) => x.n === fresh.n);
						if (i >= 0) this.rows[i] = fresh;
					});
					this.pending.clear();
					this.update_dirty();
					this.render_target_info();
					this.render_table();
					const summary = (r.applied || [])
						.filter((a) => a.action !== "unchanged")
						.map((a) => `${a.role} · ${a.doctype}: ${a.action}`)
						.slice(0, 6)
						.join("<br>");
					frappe.show_alert(
						{
							message: `${__("Saved. Frappe now enforces these rules.")}${summary ? "<br><small>" + esc(summary).replace(/&lt;br&gt;/g, "<br>") + "</small>" : ""}`,
							indicator: "green",
						},
						7
					);
					if (this.drawer_doctype && touched.includes(this.drawer_doctype)) {
						this.open_drawer(this.drawer_doctype);
					}
				})
				.catch(() => {
					// Frappe has already shown the server's message; the batch was
					// rolled back, so the pending edits stay for the admin to fix.
					frappe.show_alert({ message: __("Nothing was saved. Fix the highlighted rule and try again."), indicator: "red" });
				})
				.finally(() => frappe.dom.unfreeze());
		}

		// ------------------------------------------------------------------
		// Popover: which role should change (user view)
		// ------------------------------------------------------------------

		open_popover($cell, doctype, ptype, label) {
			const row = this.row_index.get(doctype);
			if (!row) return;
			this.popover_ctx = { doctype, ptype };
			const roles = this.scope_roles().slice().sort((a, b) => {
				const ra = row.r && row.r[a] ? 0 : 1;
				const rb = row.r && row.r[b] ? 0 : 1;
				return ra - rb || a.localeCompare(b);
			});
			const items = roles
				.map((role) => {
					const locked = this.locked_roles.has(role);
					const checked = this.role_grants(row, role).has(ptype) ? " checked" : "";
					const has_rule = row.r && row.r[role];
					const owner = row.o && row.o[role] && row.o[role].includes(ptype);
					const hint = owner ? `<small>${__("if owner")}</small>` : !has_rule ? `<small style="color:var(--text-muted)">${__("new rule")}</small>` : "";
					return `<label class="nxpi-popover-role${locked ? " is-locked" : ""}" title="${locked ? esc(__("This role's rules cannot be edited here")) : ""}">
						<input type="checkbox" data-role="${esc(role)}"${checked}${locked ? " disabled" : ""}> <span>${esc(role)}</span>${hint}
					</label>`;
				})
				.join("");
			this.$popover
				.html(
					`<div class="nxpi-popover-title">${esc(label)} · ${esc(doctype)}</div>
					<div class="nxpi-popover-sub">${__("Tick the roles that should grant this. The user gets it if any of their roles does.")}</div>
					<div class="nxpi-popover-roles">${items}</div>
					<div class="nxpi-popover-foot">
						<span>
							<button class="btn btn-xs btn-default nxpi-popover-all" data-value="1">${__("All on")}</button>
							<button class="btn btn-xs btn-default nxpi-popover-all" data-value="0">${__("All off")}</button>
						</span>
						<button class="btn btn-xs btn-primary nxpi-popover-close">${__("Done")}</button>
					</div>`
				)
				.prop("hidden", false);

			const root = this.$root.offset();
			const off = $cell.offset();
			const width = this.$popover.outerWidth();
			let left = off.left - root.left + $cell.outerWidth() / 2 - width / 2;
			left = Math.max(8, Math.min(left, this.$root.width() - width - 8));
			this.$popover.css({ top: off.top - root.top + $cell.outerHeight() + 4, left });
		}

		close_popover() {
			this.$popover.prop("hidden", true).empty();
			this.popover_ctx = null;
		}

		on_popover_checkbox(e) {
			if (!this.popover_ctx) return;
			const $input = $(e.currentTarget);
			const { doctype, ptype } = this.popover_ctx;
			this.set_pending(doctype, $input.data("role"), ptype, $input.prop("checked") ? 1 : 0);
			this.after_edit(doctype);
			this.sync_popover();
		}

		popover_set_all(value) {
			if (!this.popover_ctx) return;
			const { doctype, ptype } = this.popover_ctx;
			this.$popover.find("input[type=checkbox]:not(:disabled)").each((_, el) => {
				this.set_pending(doctype, $(el).data("role"), ptype, Number(value));
			});
			this.after_edit(doctype);
			this.sync_popover();
		}

		sync_popover() {
			if (!this.popover_ctx) return;
			const { doctype, ptype } = this.popover_ctx;
			const row = this.row_index.get(doctype);
			this.$popover.find("input[type=checkbox]").each((_, el) => {
				el.checked = this.role_grants(row, $(el).data("role")).has(ptype);
			});
		}

		// ------------------------------------------------------------------
		// Drawer: one DocType in depth
		// ------------------------------------------------------------------

		open_drawer(doctype) {
			if (!this.target) return;
			this.drawer_doctype = doctype;
			this.$body.addClass("has-drawer");
			this.$drawer.prop("hidden", false).html(`<div class="nxpi-info-sub">${__("Loading…")}</div>`);
			frappe
				.xcall(`${API}.get_doctype_detail`, {
					target_type: this.target.type,
					target: this.target.name,
					doctype,
				})
				.then((d) => {
					if (this.drawer_doctype !== doctype) return;
					this.$drawer.html(this.drawer_html(d));
				})
				.catch(() => this.close_drawer());
		}

		close_drawer() {
			this.drawer_doctype = null;
			this.$body.removeClass("has-drawer");
			this.$drawer.prop("hidden", true).empty();
		}

		drawer_html(d) {
			const t = this.data.target;
			const flags = Object.keys(FLAG_LABELS)
				.filter((k) => d.flags && d.flags[k])
				.map((k) => `<span class="nxpi-flag">${FLAG_LABELS[k]}</span>`)
				.join("");
			const customised = d.customised
				? `<span class="nxpi-flag is-customised">${__("Customised")}</span>`
				: "";
			const label_of = (pt) => {
				const col = this.columns.find((c) => c.key === pt);
				return col ? col.label : frappe.unscrub(pt);
			};
			const rules_table = (rules, empty) => {
				if (!rules || !rules.length) return `<div class="nxpi-info-sub">${empty}</div>`;
				return `<table class="nxpi-rules"><thead><tr><th>${__("Role")}</th><th>${__("Level")}</th><th>${__("Grants")}</th></tr></thead><tbody>${rules
					.map(
						(r) => `<tr>
							<td>${esc(r.role)}${r.if_owner ? ` <span class="nxpi-chip">${__("if owner")}</span>` : ""}</td>
							<td>${r.permlevel}</td>
							<td><div class="nxpi-chips">${(r.granted || []).map((g) => `<span class="nxpi-chip">${esc(label_of(g))}</span>`).join("") || `<span class="nxpi-info-sub">${__("nothing")}</span>`}</div></td>
						</tr>`
					)
					.join("")}</tbody></table>`;
			};

			let html = `<div class="nxpi-drawer-head">
				<div>
					<h4 class="nxpi-drawer-title">${esc(d.doctype)}</h4>
					<div class="nxpi-info-sub">${esc(d.module)}${d.app ? " · " + esc(d.app) : ""} ${customised}${flags}</div>
				</div>
				<button class="btn btn-default btn-xs nxpi-drawer-close" title="${esc(__("Close"))}">&times;</button>
			</div>`;
			if (d.description) html += `<p class="nxpi-drawer-desc">${esc(d.description)}</p>`;
			if (d.lock) html += `<div class="nxpi-note is-warn">${esc(d.lock)}</div>`;
			if (d.flags && d.flags.child && d.parents && d.parents.length) {
				html += `<div class="nxpi-note">${__("Used inside")}: ${esc(d.parents.join(", "))}</div>`;
			}
			if (d.na && d.na.length) {
				html += `<div class="nxpi-info-sub">${__("Never applicable here")}: ${esc(d.na.map(label_of).join(", "))}</div>`;
			}

			html += `<div><h6>${t.type === "user" ? __("Rules from this user's roles") : __("Rules for this role")}</h6>${rules_table(
				d.rules,
				__("No rule at all: nothing grants access to this DocType.")
			)}</div>`;

			if (d.standard_rules) {
				html += `<details><summary>${__("Standard rules shipped in code (before customisation)")}</summary>${rules_table(
					d.standard_rules,
					__("No standard rule for these roles.")
				)}</details>`;
			}

			if (d.live) {
				html += `<div><h6>${__("Frappe's own answer for {0}", [esc(t.name)])}</h6><div class="nxpi-live">${d.rights
					.filter((pt) => !(d.na || []).includes(pt))
					.map(
						(pt) => `<div class="nxpi-live-item is-${d.live[pt] ? 1 : 0}"><span>${esc(label_of(pt))}</span><b>${
							d.live[pt] ? GLYPH[1] : GLYPH[0]
						}</b></div>`
					)
					.join("")}</div>
					<div class="nxpi-info-sub" style="margin-top:4px">${__("Asked live through frappe.has_permission, so this is what the system enforces right now.")}</div></div>`;
			}

			if (t.type === "user" && !t.is_admin) {
				const ups = d.user_permissions || [];
				html += `<div><h6>${__("User Permissions touching this DocType")}</h6>`;
				if (!ups.length) {
					html += `<div class="nxpi-info-sub">${__("None. Row-level access is not restricted for this user here.")}</div>`;
				} else {
					html += `<table class="nxpi-rules"><thead><tr><th>${__("Allow")}</th><th>${__("Value")}</th><th>${__("Applies to")}</th></tr></thead><tbody>${ups
						.map(
							(u) => `<tr><td>${esc(u.allow)}</td><td class="nxpi-up-value">${esc(u.for_value)}${
								u.is_default ? ` <span class="nxpi-chip">${__("default")}</span>` : ""
							}</td><td>${u.apply_to_all_doctypes ? __("All DocTypes") : esc(u.applicable_for || "")}</td></tr>`
						)
						.join("")}</tbody></table>`;
				}
				html += `</div>`;
			}

			html += `<div class="nxpi-drawer-actions">
				<button class="btn btn-default btn-xs nxpi-drawer-manager">${__("Open in Role Permission Manager")}</button>
				${t.type === "user" ? `<button class="btn btn-default btn-xs nxpi-drawer-up-list">${__("User Permissions")}</button>` : ""}
			</div>`;
			return html;
		}

		// ------------------------------------------------------------------
		// User Permissions panel (the other layer, shown separately)
		// ------------------------------------------------------------------

		toggle_userperms() {
			if (!this.target || this.target.type !== "user") return;
			if (!this.$userperms.prop("hidden")) {
				this.$userperms.prop("hidden", true);
				return;
			}
			this.$userperms.prop("hidden", false).html(`<div class="nxpi-info-sub">${__("Loading…")}</div>`);
			frappe.xcall(`${API}.get_user_permissions`, { user: this.target.name }).then((d) => {
				const rows = d.rows || [];
				let body;
				if (!rows.length) {
					body = `<div class="nxpi-info-sub">${__(
						"No User Permissions. This user sees every document their roles allow; nothing is narrowed to a particular Company, Customer or other value."
					)}</div>`;
				} else {
					body = `<table class="nxpi-rules"><thead><tr>
						<th>${__("Allow (DocType)")}</th><th>${__("Value")}</th><th>${__("Applies to")}</th><th>${__("Default")}</th><th>${__("Descendants")}</th><th></th>
					</tr></thead><tbody>${rows
						.map(
							(u) => `<tr>
								<td>${esc(u.allow)}</td>
								<td class="nxpi-up-value">${esc(u.for_value)}</td>
								<td>${u.apply_to_all_doctypes ? __("All DocTypes") : esc(u.applicable_for || "")}</td>
								<td>${u.is_default ? GLYPH[1] : ""}</td>
								<td>${u.hide_descendants ? __("hidden") : __("included")}</td>
								<td><a href="/app/user-permission/${encodeURIComponent(u.name)}">${__("Open")}</a></td>
							</tr>`
						)
						.join("")}</tbody></table>`;
				}
				this.$userperms.html(`
					<div class="nxpi-userperms-head">
						<h5>${__("User Permissions for {0}", [esc(this.target.name)])} <span class="nxpi-info-sub">(${rows.length})</span></h5>
						<span>
							<button class="btn btn-default btn-xs nxpi-up-new">${__("New")}</button>
							<button class="btn btn-default btn-xs nxpi-up-manage">${__("Manage")}</button>
							<button class="btn btn-default btn-xs nxpi-up-close">&times;</button>
						</span>
					</div>
					<div class="nxpi-info-sub">${__(
						"User Permissions narrow which documents this user may see for the DocTypes above. They do not grant anything; role permissions decide the actions, these decide the rows."
					)}${d.strict ? " " + __("Strict mode is on: documents with an empty link field are hidden too.") : ""}</div>
					${body}`);
			});
		}
	}

	nexus_theme.permission_inspector.Inspector = Inspector;
})();
