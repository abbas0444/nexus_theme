// Permission Inspector — /app/permission-inspector
//
// A plain-language window onto Frappe's own role-permission records for one
// person or one role. The backend (nexus_theme/permission_inspector/api.py)
// reads through Frappe's permission helpers and writes through Custom
// DocPerm, exactly as the stock Role Permission Manager does. This file only
// draws, filters and batches edits; the answers it shows are Frappe's.
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
	const CHUNK = 150; // rows rendered per animation frame

	// Plain words for Frappe's permission flags, with a one-line explanation.
	const LABELS = {
		read: [__("View"), __("Open and look at these records.")],
		write: [__("Edit"), __("Change and save records that already exist.")],
		create: [__("Create"), __("Make new records.")],
		delete: [__("Delete"), __("Delete records.")],
		submit: [__("Submit"), __("Finalise a record so it counts. Only for record types that use submission.")],
		cancel: [__("Cancel"), __("Cancel a submitted record. Needs Submit.")],
		amend: [__("Amend"), __("Make a corrected copy of a cancelled record. Needs Edit.")],
		print: [__("Print"), __("Print these records.")],
		email: [__("Email"), __("Send these records by email.")],
		report: [__("Reports"), __("Use reports and the report builder on these records.")],
		import: [__("Import"), __("Bring records in from a spreadsheet with Data Import. Needs Create.")],
		export: [__("Export"), __("Download these records to a spreadsheet.")],
		share: [__("Share"), __("Share one record with another person.")],
		select: [__("Pick in lists"), __("Choose these records in drop-downs without being able to open them. Comes free with View.")],
		mask: [__("See masked values"), __("See the real value of fields that show as asterisks to others.")],
	};
	const ESSENTIAL = ["read", "write", "create", "delete", "submit", "cancel"];
	const STATE_TEXT = { 1: __("Yes"), 0: __("No"), 2: __("Own only"), na: "–" };

	// Frappe's rule dependencies. Ticking a flag pulls in what it needs;
	// clearing one drops what needed it. The server applies the same rules.
	const NEEDS = { cancel: ["submit", "write"], submit: ["write"], amend: ["write"], import: ["create"] };
	const DEPENDENTS = { write: ["submit", "cancel", "amend"], submit: ["cancel"], create: ["import"] };

	const FLAG_WORDS = {
		single: __("single record"),
		submittable: __("uses submission"),
		tree: __("tree"),
		virtual: __("virtual"),
		custom: __("custom"),
		child: __("child table"),
	};

	class Inspector {
		constructor(wrapper, page) {
			this.wrapper = wrapper;
			this.page = page;
			this.$root = $(frappe.render_template("permission_inspector", {}));
			$(page.main).addClass("nxpi-page").empty().append(this.$root);

			this.options = null;
			this.kind = "user";
			this.target = null; // { type: "user"|"role", name }
			this.data = null;
			this.rows = [];
			this.row_index = new Map();
			this.pending = new Map(); // key -> { doctype, role, ptype, value }
			this.editing = false;
			this.filters = { search: "", module: "", show: "all", columns: "essential", child: false };
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
			this.$summary = $(".nxpi-summary");
			this.$userperms = $(".nxpi-userperms");
			this.$step_matrix = $(".nxpi-step-matrix");
			this.$matrix_title = $(".nxpi-matrix-title");
			this.$matrix_sub = $(".nxpi-matrix-sub");
			this.$empty = $(".nxpi-empty");
			this.$help = $(".nxpi-help");
			this.$thead = $(".nxpi-table thead");
			this.$tbody = $(".nxpi-table tbody");
			this.$wrap = $(".nxpi-matrix-wrap");
			this.$no_rows = $(".nxpi-no-rows");
			this.$body = $(".nxpi-body");
			this.$drawer = $(".nxpi-drawer");
			this.$count = $(".nxpi-count");
			this.$edit_btn = $(".nxpi-edit");
			this.$editbar = $(".nxpi-editbar");
			this.$editbar_text = $(".nxpi-editbar-text");
			this.$module = $(".nxpi-module");
			this.$show = $(".nxpi-show");
			this.$columns = $(".nxpi-columns");
			this.$search = $(".nxpi-search");
			this.$child = $(".nxpi-child");
			this.$clear = $(".nxpi-clear");
			this.$savebar = $(".nxpi-savebar");
			this.$savebar_text = $(".nxpi-savebar-text");
		}

		make_controls() {
			this.user_control = frappe.ui.form.make_control({
				df: {
					fieldtype: "Link",
					options: "User",
					fieldname: "nxpi_user",
					placeholder: __("Type a name or email"),
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
					placeholder: __("Type a role name, e.g. Accounts User"),
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
			this.$root.on("click", ".nxpi-seg", (e) => this.set_kind($(e.currentTarget).data("kind")));
			this.$clear.on("click", () => this.clear());
			this.$root.on("click", ".nxpi-help-btn", () => this.$help.prop("hidden", !this.$help.prop("hidden")));

			const debounced = frappe.utils.debounce(() => {
				this.filters.search = (this.$search.val() || "").trim().toLowerCase();
				this.render_table();
			}, 150);
			this.$search.on("input", debounced);
			this.$module.on("change", () => {
				this.filters.module = this.$module.val();
				this.render_table();
			});
			this.$show.on("change", () => {
				this.filters.show = this.$show.val();
				this.render_table();
			});
			this.$columns.on("change", () => {
				this.filters.columns = this.$columns.val();
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

			// Summary actions
			this.$root.on("click", ".nxpi-open-userperms", () => this.toggle_userperms());
			this.$root.on("click", ".nxpi-open-manager", () => frappe.set_route("permission-manager"));
			this.$root.on("click", ".nxpi-open-target", () => {
				if (!this.target) return;
				frappe.set_route("Form", this.target.type === "user" ? "User" : "Role", this.target.name);
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

			// Save bar
			this.$root.on("click", ".nxpi-save", () => this.confirm_and_save());
			this.$root.on("click", ".nxpi-discard", () => this.discard());

			$(document).on("keydown.nxpi", (e) => {
				if (e.key === "Escape" && this.drawer_doctype) this.close_drawer();
			});
			$(window).on("beforeunload.nxpi", () => {
				if (this.pending.size) return __("You have unsaved permission changes.");
			});
		}

		load_options() {
			frappe.xcall(`${API}.get_options`).then((opts) => {
				this.options = opts;
			});
		}

		apply_route_options() {
			const ro = frappe.route_options;
			if (!ro) return;
			const kind = ro.user ? "user" : ro.role ? "role" : null;
			if (!kind) return;
			frappe.route_options = null;
			const value = ro[kind];
			this.set_kind(kind);
			this.silently(() => this.control(kind).set_value(value));
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

		control(kind) {
			return kind === "user" ? this.user_control : this.role_control;
		}

		// ------------------------------------------------------------------
		// Picking a person or a role
		// ------------------------------------------------------------------

		set_kind(kind) {
			if (kind !== "user" && kind !== "role") return;
			this.kind = kind;
			this.$root.find(".nxpi-seg").each((_, el) => {
				$(el).toggleClass("is-active", $(el).data("kind") === kind);
			});
			this.$root.find('[data-control="user"]').prop("hidden", kind !== "user");
			this.$root.find('[data-control="role"]').prop("hidden", kind !== "role");
			if (this.target && this.target.type !== kind) {
				// Switching kind while looking at the other: start fresh.
				this.clear(true);
			}
		}

		on_pick(kind) {
			if (this._silent) return;
			const value = this.control(kind).get_value();
			if (!value) {
				if (this.target && this.target.type === kind) this.clear(true);
				return;
			}
			this.select(kind, value);
		}

		select(kind, name) {
			if (this.pending.size) {
				this.block_for_unsaved();
				return;
			}
			this.target = { type: kind, name };
			this.pending.clear();
			this.editing = false;
			this.close_drawer();
			this.$userperms.prop("hidden", true).empty();
			this.$clear.prop("hidden", false);
			this.update_dirty();
			this.reload();
		}

		block_for_unsaved() {
			frappe.show_alert({
				message: __("You have unsaved changes. Save or discard them first."),
				indicator: "orange",
			});
		}

		clear(keep_kind) {
			if (this.pending.size) {
				this.block_for_unsaved();
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
			this.$userperms.prop("hidden", true).empty();
			this.$summary.prop("hidden", true).empty();
			this.$step_matrix.prop("hidden", true);
			this.$empty.prop("hidden", false);
			this.$clear.prop("hidden", true);
			this.update_dirty();
			if (!keep_kind) this.set_kind("user");
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
					this.render_summary();
					this.render_matrix_heading();
					this.fill_module_select();
					this.$empty.prop("hidden", true);
					this.$step_matrix.prop("hidden", false);
					this.update_edit_button();
					this.render_table();
					if (this.drawer_doctype && this.row_index.has(this.drawer_doctype)) {
						this.open_drawer(this.drawer_doctype);
					} else {
						this.close_drawer();
					}
				})
				.catch(() => {
					this.$step_matrix.prop("hidden", true);
					this.$summary.prop("hidden", true);
					this.$empty.prop("hidden", false);
				})
				.finally(() => frappe.dom.unfreeze());
		}

		refresh_from_server() {
			if (!this.target) return;
			if (this.pending.size) {
				this.block_for_unsaved();
				return;
			}
			frappe
				.xcall(`${API}.refresh_cache`, { target_type: this.target.type, target: this.target.name })
				.then(() => this.reload());
		}

		// ------------------------------------------------------------------
		// Labels
		// ------------------------------------------------------------------

		label(ptype) {
			if (LABELS[ptype]) return LABELS[ptype][0];
			return frappe.unscrub(ptype);
		}

		explain(ptype) {
			if (LABELS[ptype]) return LABELS[ptype][1];
			return __("A custom permission type defined for this record type.");
		}

		target_label() {
			const t = this.data.target;
			return t.type === "user" ? t.label : __("people with the role {0}", [t.label]);
		}

		// ------------------------------------------------------------------
		// Summary
		// ------------------------------------------------------------------

		stats() {
			const keys = ["read", "write", "create", "delete", "submit"];
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

		sentence(s) {
			const t = this.data.target;
			const who = t.type === "user" ? esc(t.label) : __("People with the role {0}", [esc(t.label)]);
			if (t.type === "user" && t.is_admin) {
				return __("{0} is the Administrator and can do everything, everywhere. Nothing here can limit that.", [who]);
			}
			if (t.type === "user" && !t.roles.length) {
				return __("{0} has no roles yet, so no role gives them anything to do.", [who]);
			}
			return __("{0} can view <b>{1}</b> types of records, edit <b>{2}</b>, create <b>{3}</b> and delete <b>{4}</b>.", [
				who,
				s.read,
				s.write,
				s.create,
				s.delete,
			]);
		}

		stats_html(s) {
			const tile = (n, label) => `<div class="nxpi-stat"><b>${n}</b><span>${label}</span></div>`;
			return `<div class="nxpi-stats">
				${tile(s.read, __("can view"))}
				${tile(s.write, __("can edit"))}
				${tile(s.create, __("can create"))}
				${tile(s.delete, __("can delete"))}
				${tile(s.submit, __("can submit"))}
				${tile(s.total, __("record types"))}
			</div>`;
		}

		render_summary() {
			const t = this.data.target;
			const s = this.stats();
			let html = "";

			if (t.type === "user") {
				const badges = [];
				badges.push(
					t.enabled
						? `<span class="indicator-pill green">${__("Active")}</span>`
						: `<span class="indicator-pill red">${__("Disabled")}</span>`
				);
				if (t.is_system_manager && !t.is_admin) {
					badges.push(`<span class="indicator-pill blue" title="${esc(__("Can manage users and permissions"))}">${__("System Manager")}</span>`);
				}
				const chips = t.roles
					.map((r) => {
						const cls = ["nxpi-chip"];
						let title = "";
						if (t.disabled_roles.includes(r)) {
							cls.push("is-disabled");
							title = __("This role is switched off, so it gives nothing");
						}
						return `<span class="${cls.join(" ")}" title="${esc(title)}">${esc(r)}</span>`;
					})
					.join("");

				let notes = "";
				if (t.is_admin) {
					notes += `<div class="nxpi-note is-warn">${__(
						"The Administrator account is above the permission system. Every row below shows Yes, and editing is switched off."
					)}</div>`;
				}
				if (!t.enabled) {
					notes += `<div class="nxpi-note is-warn">${__(
						"This person is disabled and cannot log in. The table shows what they would get if they were enabled again."
					)}</div>`;
				}
				if (t.blocked_modules && t.blocked_modules.length) {
					notes += `<div class="nxpi-note">${__("Modules hidden for this person on their User record: {0}", [
						esc(t.blocked_modules.join(", ")),
					])}</div>`;
				}

				html = `
					<div class="nxpi-summary-main">
						<div class="nxpi-summary-title">${esc(t.label)} <span class="nxpi-summary-id">${esc(t.name)}</span> ${badges.join(" ")}</div>
						<div class="nxpi-summary-sentence">${this.sentence(s)}</div>
						<div class="nxpi-chips"><span class="nxpi-roles-label">${__("Roles")}:</span>${
							chips || `<span class="nxpi-summary-id">${__("none")}</span>`
						}</div>
						${notes}
					</div>
					${this.stats_html(s)}
					<div class="nxpi-summary-actions">
						<button class="btn btn-default btn-sm nxpi-open-userperms">${__("Which records can they see?")} (${t.user_permission_count})</button>
						<button class="btn btn-default btn-sm nxpi-open-target">${__("Open this user")}</button>
						<button class="btn btn-default btn-sm nxpi-open-manager">${__("Open Frappe's Role Permission Manager")}</button>
					</div>`;
			} else {
				const badges = [];
				badges.push(
					t.disabled
						? `<span class="indicator-pill red">${__("Switched off")}</span>`
						: `<span class="indicator-pill green">${__("Active")}</span>`
				);
				if (t.is_automatic) {
					badges.push(`<span class="indicator-pill blue" title="${esc(__("Frappe gives this role to users automatically"))}">${__("Automatic")}</span>`);
				}
				let notes = "";
				if (this.locked_roles.has(t.name)) {
					notes += `<div class="nxpi-note is-warn">${__("This role is managed by Frappe itself, so it cannot be changed from here.")}</div>`;
				}
				if (t.name === "System Manager") {
					notes += `<div class="nxpi-note">${__(
						"System Managers can additionally import and export any record type and manage permissions, on top of the rows below."
					)}</div>`;
				}
				const users = t.users.length
					? esc(t.users.slice(0, 10).join(", ")) + (t.user_count > 10 ? ` +${t.user_count - 10}` : "")
					: __("nobody yet");

				html = `
					<div class="nxpi-summary-main">
						<div class="nxpi-summary-title">${esc(t.label)} ${badges.join(" ")}</div>
						<div class="nxpi-summary-sentence">${this.sentence(s)}</div>
						<div class="nxpi-summary-id" title="${users}">${__("Who has this role")}: ${users}</div>
						${notes}
					</div>
					${this.stats_html(s)}
					<div class="nxpi-summary-actions">
						<button class="btn btn-default btn-sm nxpi-open-target">${__("Open this role")}</button>
						<button class="btn btn-default btn-sm nxpi-open-manager">${__("Open Frappe's Role Permission Manager")}</button>
					</div>`;
			}
			this.$summary.html(html).prop("hidden", false);
		}

		refresh_summary() {
			if (this.data) this.render_summary();
		}

		render_matrix_heading() {
			const t = this.data.target;
			if (t.type === "user") {
				this.$matrix_title.text(__("What can {0} do?", [t.label]));
				this.$matrix_sub.text(
					__("Each row is one type of record. The last column tells you which role gives the permission.")
				);
			} else {
				this.$matrix_title.text(__("What does the role {0} allow?", [t.label]));
				this.$matrix_sub.text(__("Each row is one type of record and what this role allows on it."));
			}
		}

		// ------------------------------------------------------------------
		// Filters and columns
		// ------------------------------------------------------------------

		fill_module_select() {
			const current = this.filters.module;
			const modules = Array.from(new Set(this.rows.map((r) => r.m))).sort((a, b) => a.localeCompare(b));
			this.$module.empty().append(`<option value="">${__("All modules")}</option>`);
			modules.forEach((m) => this.$module.append(`<option value="${esc(m)}">${esc(m)}</option>`));
			if (modules.includes(current)) this.$module.val(current);
			else this.filters.module = "";
		}

		custom_ptypes() {
			const set = new Set();
			this.rows.forEach((r) => (r.x || []).forEach((x) => set.add(x)));
			return Array.from(set).sort();
		}

		visible_columns() {
			const all = this.columns.map((c) => c.key);
			if (this.filters.columns === "essential") {
				return ESSENTIAL.filter((k) => all.includes(k));
			}
			return all.concat(this.custom_ptypes());
		}

		visible_rows() {
			const f = this.filters;
			const rights = this.data.rights;
			const rows = this.rows.filter((row) => {
				if (f.search && !(row.n.toLowerCase().includes(f.search) || row.m.toLowerCase().includes(f.search))) {
					return false;
				}
				if (f.module && row.m !== f.module) return false;
				if (f.show === "customised") return !!row.c;
				if (f.show === "changed") return this.row_has_pending(row.n);
				if (f.show === "all") return true;
				const p = this.effective(row).perms;
				const any_on = rights.concat(row.x || []).some((k) => p[k]);
				return f.show === "enabled" ? any_on : !any_on;
			});
			// Grouped by module, then by name, so the table reads like a book.
			return rows.sort((a, b) => a.m.localeCompare(b.m) || a.n.localeCompare(b.n));
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
			return `${doctype}${role}${ptype}`;
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

		render_head(cols) {
			let html = `<tr><th class="nxpi-h-dt">${__("Record type")}</th>`;
			cols.forEach((key) => {
				html += `<th title="${esc(this.explain(key))}">${esc(this.label(key))}</th>`;
			});
			html += `<th class="nxpi-h-src">${this.data.target.type === "user" ? __("Because of") : __("Note")}</th></tr>`;
			this.$thead.html(html);
		}

		render_table() {
			if (!this.data) return;
			const cols = this.visible_columns();
			this.render_head(cols);
			const visible = this.visible_rows();
			this.$count.text(__("{0} of {1} record types", [visible.length, this.rows.length]));
			this.$no_rows.prop("hidden", visible.length > 0);
			this.$tbody.empty();

			const token = ++this.render_token;
			const span = cols.length + 2;
			const groups = {};
			visible.forEach((r) => (groups[r.m] = (groups[r.m] || 0) + 1));
			let i = 0;
			let last_module = null;
			const step = () => {
				if (token !== this.render_token) return;
				const parts = [];
				const end = Math.min(i + CHUNK, visible.length);
				for (; i < end; i++) {
					const row = visible[i];
					if (row.m !== last_module) {
						last_module = row.m;
						parts.push(
							`<tr class="nxpi-group"><td colspan="${span}">${esc(row.m)} · ${__("{0} record types", [groups[row.m]])}</td></tr>`
						);
					}
					parts.push(this.row_html(row, cols));
				}
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
			$old.replaceWith(this.row_html(row, this.visible_columns()));
		}

		row_flags_html(row) {
			const words = Object.keys(FLAG_WORDS)
				.filter((k) => row.f && row.f[k] && k !== "submittable")
				.map((k) => `<span class="nxpi-flag">${FLAG_WORDS[k]}</span>`);
			if (row.c) {
				words.unshift(
					`<span class="nxpi-flag is-customised" title="${esc(
						__("Someone changed the rules for this record type; they no longer match the standard ones")
					)}">${__("customised")}</span>`
				);
			}
			return words.join("");
		}

		row_html(row, cols) {
			const ev = this.effective(row);
			const changed = this.row_has_pending(row.n);
			const lock = row.lock ? ` title="${esc(row.lock)}"` : "";
			let tds = `<td class="nxpi-dt"${lock}><a href="#" class="nxpi-dt-link" data-dt="${esc(row.n)}">${esc(row.n)}</a>${this.row_flags_html(row)}</td>`;
			cols.forEach((key) => {
				tds += this.cell_html(row, key, ev);
			});
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

		cell_title(row, ptype, state, ev) {
			const label = this.label(ptype);
			let text;
			if (state === "na") text = __("{0}: does not apply to this record type", [label]);
			else if (state === 2) text = __("{0}: only on records they created themselves", [label]);
			else if (state === 1) text = __("{0}: allowed", [label]);
			else text = __("{0}: not allowed", [label]);
			if (state !== "na" && state !== 0) {
				if (this.data.target.type === "user") {
					const src = (ev.sources && ev.sources[ptype]) || [];
					if (src.length) text += `\n${__("Because of")}: ${src.join(", ")}`;
				}
			}
			if (this.editing && this.is_cell_editable(row, ptype)) {
				text += `\n${this.data.target.type === "user" ? __("Click to choose which role should change") : __("Click to switch between Yes and No")}`;
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

		cell_html(row, ptype, ev) {
			const state = this.cell_state(row, ptype, ev);
			const editable = this.is_cell_editable(row, ptype);
			const cls = ["nxpi-cell"];
			if (editable) cls.push("is-editable");
			const pending = this.scope_roles().some((role) => this.pending_value(row.n, role, ptype) !== null);
			if (pending) cls.push("is-pending");
			let own_mark = "";
			if (this.data.target.type === "role" && state !== "na") {
				const role = this.data.target.name;
				if (row.o && row.o[role] && row.o[role].includes(ptype) && state !== 2) {
					own_mark = `<span class="nxpi-own-mark" title="${esc(__("Also allowed on their own records by a separate rule"))}">${__("+ own")}</span>`;
				}
			}
			return `<td class="${cls.join(" ")}" data-dt="${esc(row.n)}" data-pt="${esc(ptype)}" title="${esc(
				this.cell_title(row, ptype, state, ev)
			)}"><span class="nxpi-pill is-${state}">${STATE_TEXT[state]}</span>${own_mark}</td>`;
		}

		source_html(row, ev) {
			if (this.data.target.type === "role") {
				const role = this.data.target.name;
				if (row.o && row.o[role] && !(row.r && row.r[role])) return __("only on their own records");
				if (!(row.r && row.r[role]) && !(row.o && row.o[role])) return `<span>${__("no rule")}</span>`;
				return "";
			}
			if (this.data.target.is_admin) return __("Administrator");
			const roles = new Set();
			Object.keys(ev.sources || {}).forEach((pt) => {
				(ev.sources[pt] || []).forEach((s) => {
					if (s !== __("implied by Read")) roles.add(s);
				});
			});
			const list = Array.from(roles).sort();
			if (!list.length) return `<span>${__("no role allows this")}</span>`;
			const shown = list.slice(0, 3).map((r) => `<span class="nxpi-chip" title="${esc(r)}">${esc(r)}</span>`);
			if (list.length > 3) {
				shown.push(`<span class="nxpi-chip" title="${esc(list.slice(3).join(", "))}">+${list.length - 3}</span>`);
			}
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
				.toggleClass("btn-primary", !this.editing)
				.toggleClass("btn-default", this.editing)
				.text(this.editing ? __("Stop editing") : __("Change permissions"))
				.attr(
					"title",
					blocked
						? t.type === "user"
							? __("The Administrator cannot be limited")
							: __("This role is managed by Frappe itself")
						: ""
				);
			this.$editbar.prop("hidden", !this.editing);
			if (this.editing) {
				this.$editbar_text.text(
					t.type === "user"
						? __("Click any Yes or No. You will be asked which of this person's roles should change. Nothing is saved until you press Save changes.")
						: __("Click any Yes or No to switch it. Nothing is saved until you press Save changes.")
				);
			}
		}

		toggle_edit() {
			if (!this.data) return;
			this.editing = !this.editing;
			this.update_edit_button();
			this.render_table();
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

		cascade_note(ptype, value) {
			const linked = value ? NEEDS[ptype] || [] : DEPENDENTS[ptype] || [];
			if (!linked.length) return "";
			const names = linked.map((k) => this.label(k)).join(", ");
			return value
				? __("Turning {0} on also turns on {1}, because Frappe requires it.", [this.label(ptype), names])
				: __("Turning {0} off also turns off {1}, because they depend on it.", [this.label(ptype), names]);
		}

		on_cell_click(e) {
			const $cell = $(e.currentTarget);
			const doctype = $cell.data("dt");
			const ptype = $cell.data("pt");
			const row = this.row_index.get(doctype);
			if (!row) return;
			if (this.data.target.type === "role") {
				const role = this.data.target.name;
				const now = this.role_grants(row, role).has(ptype) ? 1 : 0;
				this.set_pending(doctype, role, ptype, now ? 0 : 1);
				const note = this.cascade_note(ptype, now ? 0 : 1);
				if (note) frappe.show_alert({ message: note, indicator: "blue" }, 4);
				this.after_edit(doctype);
				return;
			}
			this.open_role_dialog(row, ptype);
		}

		after_edit(doctype) {
			this.rerender_row(doctype);
			this.update_dirty();
			this.refresh_summary();
		}

		// The user view never guesses: the admin picks which role changes.
		open_role_dialog(row, ptype) {
			const t = this.data.target;
			const label = this.label(ptype);
			const ev = this.effective(row);
			const allowed_now = !!ev.perms[ptype];
			const roles = this.scope_roles()
				.slice()
				.sort((a, b) => {
					const ra = row.r && row.r[a] ? 0 : 1;
					const rb = row.r && row.r[b] ? 0 : 1;
					return ra - rb || a.localeCompare(b);
				});

			const items = roles
				.map((role) => {
					const locked = this.locked_roles.has(role);
					const checked = this.role_grants(row, role).has(ptype);
					const has_rule = row.r && row.r[role];
					const owner = row.o && row.o[role] && row.o[role].includes(ptype);
					let hint = "";
					if (locked) hint = __("managed by Frappe");
					else if (owner && !checked) hint = __("own records only");
					else if (!has_rule) hint = __("no rule yet for this record type");
					return `<label class="nxpi-dialog-role${locked ? " is-locked" : ""}">
						<input type="checkbox" data-role="${esc(role)}"${checked ? " checked" : ""}${locked ? " disabled" : ""}>
						<span>${esc(role)}</span>${hint ? `<small>${esc(hint)}</small>` : ""}
					</label>`;
				})
				.join("");

			const intro = allowed_now
				? __("{0} can <b>{1}</b> {2} because of the roles ticked below.", [esc(t.label), esc(label), esc(row.n)])
				: __("{0} cannot <b>{1}</b> {2} at the moment. Tick the role that should allow it.", [
						esc(t.label),
						esc(label),
						esc(row.n),
				  ]);
			const body = `<div class="nxpi-dialog">
				<p>${intro}</p>
				<div class="nxpi-dialog-roles">${items}</div>
				<p class="text-muted">${__(
					"Permissions live on roles, not on people. Ticking or unticking a role changes that role for everyone who has it."
				)}</p>
				${
					this.cascade_note(ptype, 1) || this.cascade_note(ptype, 0)
						? `<p class="text-muted">${esc(this.cascade_note(ptype, 1))} ${esc(this.cascade_note(ptype, 0))}</p>`
						: ""
				}
			</div>`;

			const d = new frappe.ui.Dialog({
				title: __("{0} on {1}", [label, row.n]),
				fields: [{ fieldtype: "HTML", fieldname: "body", options: body }],
				primary_action_label: __("Apply"),
				primary_action: () => {
					d.$wrapper.find("input[type=checkbox]:not(:disabled)").each((_, el) => {
						this.set_pending(row.n, $(el).data("role"), ptype, el.checked ? 1 : 0);
					});
					d.hide();
					this.after_edit(row.n);
				},
			});
			d.show();
		}

		// ------------------------------------------------------------------
		// Unsaved changes, save, discard
		// ------------------------------------------------------------------

		update_dirty() {
			const n = this.pending.size;
			this.$savebar.prop("hidden", !n);
			if (n) {
				this.$savebar_text.html(
					__("<b>{0}</b> unsaved change(s). Nothing has been applied yet.", [n])
				);
				this.page.set_indicator(__("{0} unsaved", [n]), "orange");
			} else {
				this.page.clear_indicator();
			}
		}

		change_lines() {
			// Group pending edits per role and record type so the confirmation
			// reads like a sentence, not a diff.
			const grouped = {};
			this.pending.forEach((ch) => {
				const key = `${ch.role}${ch.doctype}`;
				grouped[key] = grouped[key] || { role: ch.role, doctype: ch.doctype, on: [], off: [] };
				(ch.value ? grouped[key].on : grouped[key].off).push(this.label(ch.ptype));
			});
			return Object.values(grouped)
				.sort((a, b) => a.role.localeCompare(b.role) || a.doctype.localeCompare(b.doctype))
				.map((g) => {
					const bits = [];
					if (g.on.length) bits.push(__("will be able to {0}", [g.on.join(", ")]));
					if (g.off.length) bits.push(__("will no longer be able to {0}", [g.off.join(", ")]));
					return __("Everyone with the role <b>{0}</b> {1} on <b>{2}</b>.", [esc(g.role), bits.join(` ${__("and")} `), esc(g.doctype)]);
				});
		}

		confirm_and_save() {
			if (!this.pending.size) return;
			const lines = this.change_lines();
			const html = `<div class="nxpi-dialog"><p>${__("You are about to change these role permissions:")}</p>
				<ul class="nxpi-dialog-list">${lines.map((l) => `<li>${l}</li>`).join("")}</ul>
				<p class="text-muted">${__("Frappe will enforce this immediately for everyone who has these roles.")}</p></div>`;
			frappe.confirm(html, () => this.save());
		}

		discard() {
			if (!this.pending.size) return;
			const touched = Array.from(new Set(Array.from(this.pending.values()).map((c) => c.doctype)));
			this.pending.clear();
			this.update_dirty();
			if (this.filters.show === "changed") this.render_table();
			else touched.forEach((dt) => this.rerender_row(dt));
			this.refresh_summary();
			frappe.show_alert({ message: __("Changes discarded. Nothing was saved."), indicator: "blue" });
		}

		save() {
			if (!this.pending.size || !this.target) return;
			const changes = Array.from(this.pending.values());
			frappe.dom.freeze(__("Saving…"));
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
					this.render_summary();
					this.render_table();
					frappe.show_alert(
						{
							message: __("Saved. The new permissions are in force now."),
							indicator: "green",
						},
						6
					);
					if (this.drawer_doctype && touched.includes(this.drawer_doctype)) {
						this.open_drawer(this.drawer_doctype);
					}
				})
				.catch(() => {
					// Frappe has shown the server's message; nothing was saved and
					// the pending edits stay so the admin can fix and retry.
					frappe.show_alert({ message: __("Nothing was saved. Please check the message and try again."), indicator: "red" });
				})
				.finally(() => frappe.dom.unfreeze());
		}

		// ------------------------------------------------------------------
		// Drawer: one record type in depth
		// ------------------------------------------------------------------

		open_drawer(doctype) {
			if (!this.target) return;
			this.drawer_doctype = doctype;
			this.$body.addClass("has-drawer");
			this.$drawer.prop("hidden", false).html(`<div class="nxpi-drawer-sub">${__("Loading…")}</div>`);
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
			const row = this.row_index.get(d.doctype);
			const flags = Object.keys(FLAG_WORDS)
				.filter((k) => d.flags && d.flags[k])
				.map((k) => FLAG_WORDS[k]);
			const pill = (state) => `<span class="nxpi-pill is-${state}">${STATE_TEXT[state]}</span>`;
			const chips = (keys) =>
				`<div class="nxpi-chips">${(keys || [])
					.map((k) => `<span class="nxpi-chip">${esc(this.label(k))}</span>`)
					.join("")}</div>`;

			let html = `<div class="nxpi-drawer-head">
				<div>
					<h4 class="nxpi-drawer-title">${esc(d.doctype)}</h4>
					<div class="nxpi-drawer-sub">${esc(d.module)}${flags.length ? " · " + esc(flags.join(", ")) : ""}${
						d.customised ? ` · <span class="nxpi-flag is-customised">${__("customised")}</span>` : ""
					}</div>
				</div>
				<button class="btn btn-default btn-xs nxpi-drawer-close" title="${esc(__("Close"))}">&times;</button>
			</div>`;
			if (d.description) html += `<p>${esc(d.description)}</p>`;
			if (d.lock) html += `<div class="nxpi-note is-warn">${esc(d.lock)}</div>`;
			if (d.flags && d.flags.child && d.parents && d.parents.length) {
				html += `<div class="nxpi-note">${__("Used inside")}: ${esc(d.parents.join(", "))}</div>`;
			}

			// What can they do here?
			const applicable = d.rights.filter((pt) => !(d.na || []).includes(pt));
			const state_of = (pt) => {
				if (d.live) return d.live[pt] ? 1 : 0;
				if (!row) return 0;
				return this.cell_state(row, pt, this.effective(row));
			};
			html += `<div><h6>${
				t.type === "user" ? __("What can {0} do here?", [esc(t.label)]) : __("What does this role allow here?")
			}</h6>
				<div class="nxpi-actions-grid">${applicable
					.map((pt) => `<div class="nxpi-action-item"><span title="${esc(this.explain(pt))}">${esc(this.label(pt))}</span>${pill(state_of(pt))}</div>`)
					.join("")}</div>
				${
					d.live
						? `<p style="margin-top:6px">${__("Checked live with Frappe, so this is exactly what the system enforces right now.")}</p>`
						: ""
				}
			</div>`;

			// Why?
			const level0 = (d.rules || []).filter((r) => r.permlevel === 0);
			const higher = (d.rules || []).filter((r) => r.permlevel > 0);
			html += `<div><h6>${__("Why?")}</h6>`;
			if (!level0.length) {
				html += `<p>${
					t.type === "user"
						? __("None of this person's roles has a rule for this record type, so they get nothing here.")
						: __("This role has no rule for this record type, so it allows nothing here.")
				}</p>`;
			} else {
				html += `<div class="nxpi-reasons">${level0
					.map(
						(r) => `<div class="nxpi-reason">
							<b>${__("Role {0} allows", [esc(r.role)])}${r.if_owner ? ` <span class="nxpi-pill is-2">${__("Own only")}</span>` : ""}</b>
							${r.granted.length ? chips(r.granted) : `<span class="text-muted">${__("nothing")}</span>`}
						</div>`
					)
					.join("")}</div>`;
			}
			if (higher.length) {
				html += `<p style="margin-top:8px">${__("Extra field-level rules")}: ${higher
					.map((r) => `${esc(r.role)} (${__("level {0}", [r.permlevel])}: ${r.granted.map((k) => esc(this.label(k))).join(", ")})`)
					.join("; ")}</p>`;
			}
			html += `</div>`;

			// Which records?
			if (t.type === "user" && !t.is_admin) {
				const ups = d.user_permissions || [];
				html += `<div><h6>${__("Which records?")}</h6>`;
				if (!ups.length) {
					html += `<p>${__("No restriction. Any record their roles allow.")}</p>`;
				} else {
					html += `<div class="nxpi-reasons">${ups
						.map(
							(u) => `<div class="nxpi-reason">${__("Only where <b>{0}</b> is <b>{1}</b>", [esc(u.allow), esc(u.for_value)])}${
								u.apply_to_all_doctypes ? "" : ` (${__("for {0} only", [esc(u.applicable_for || "")])})`
							}</div>`
						)
						.join("")}</div>`;
				}
				html += `</div>`;
			}

			if (d.standard_rules) {
				html += `<details><summary>${__("Standard rules before they were customised")}</summary>
					<table class="nxpi-rules"><thead><tr><th>${__("Role")}</th><th>${__("Allowed")}</th></tr></thead><tbody>${d.standard_rules
						.filter((r) => r.permlevel === 0)
						.map(
							(r) => `<tr><td>${esc(r.role)}${r.if_owner ? ` (${__("own only")})` : ""}</td><td>${
								r.granted.map((k) => esc(this.label(k))).join(", ") || __("nothing")
							}</td></tr>`
						)
						.join("")}</tbody></table></details>`;
			}

			html += `<div class="nxpi-drawer-actions">
				<button class="btn btn-default btn-xs nxpi-drawer-manager">${__("Open in Frappe's Role Permission Manager")}</button>
				${t.type === "user" ? `<button class="btn btn-default btn-xs nxpi-drawer-up-list">${__("Manage which records")}</button>` : ""}
			</div>`;
			return html;
		}

		// ------------------------------------------------------------------
		// Which records can they see? (User Permissions)
		// ------------------------------------------------------------------

		toggle_userperms() {
			if (!this.target || this.target.type !== "user") return;
			if (!this.$userperms.prop("hidden")) {
				this.$userperms.prop("hidden", true);
				return;
			}
			this.$userperms.prop("hidden", false).html(`<p>${__("Loading…")}</p>`);
			frappe.xcall(`${API}.get_user_permissions`, { user: this.target.name }).then((d) => {
				const rows = d.rows || [];
				const t = this.data.target;
				let body;
				if (!rows.length) {
					body = `<p>${__(
						"No restrictions. {0} can open any record their roles allow, in every Company, Customer and so on.",
						[esc(t.label)]
					)}</p>`;
				} else {
					body = `<table class="nxpi-rules"><thead><tr>
						<th>${__("Limited to")}</th><th>${__("Value")}</th><th>${__("Applies to")}</th><th>${__("Default")}</th><th>${__("Sub-records")}</th><th></th>
					</tr></thead><tbody>${rows
						.map(
							(u) => `<tr>
								<td>${esc(u.allow)}</td>
								<td><b>${esc(u.for_value)}</b></td>
								<td>${u.apply_to_all_doctypes ? __("Every record type") : esc(u.applicable_for || "")}</td>
								<td>${u.is_default ? __("Yes") : ""}</td>
								<td>${u.hide_descendants ? __("hidden") : __("included")}</td>
								<td><a href="/app/user-permission/${encodeURIComponent(u.name)}">${__("Open")}</a></td>
							</tr>`
						)
						.join("")}</tbody></table>`;
				}
				this.$userperms.html(`
					<div class="nxpi-userperms-head">
						<h5>${__("Which records can {0} see?", [esc(t.label)])}</h5>
						<span>
							<button class="btn btn-default btn-xs nxpi-up-new">${__("Add a restriction")}</button>
							<button class="btn btn-default btn-xs nxpi-up-manage">${__("Manage all")}</button>
							<button class="btn btn-default btn-xs nxpi-up-close">&times;</button>
						</span>
					</div>
					<p>${__(
						"These are User Permissions. They never add abilities; they only narrow which records this person may see, for example one Company or one Customer. The abilities themselves come from the roles in the table below."
					)}${d.strict ? " " + __("Strict mode is on: records with an empty link field are hidden too.") : ""}</p>
					${body}`);
			});
		}
	}

	nexus_theme.permission_inspector.Inspector = Inspector;
})();
