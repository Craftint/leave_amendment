import frappe
from hrms.hr.doctype.leave_application.leave_application import get_allocation_expiry_for_cf_leaves
from hrms.hr.doctype.leave_application.leave_application import get_number_of_leave_days
from hrms.hr.doctype.leave_ledger_entry.leave_ledger_entry import get_previous_expiry_ledger_entry
from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee


@frappe.whitelist()
def amend_leaves(application=None,from_date=None):
	leave_appln = frappe.get_doc("Leave Application",application)
	from_date = frappe.utils.getdate(from_date)
	manage_leave_ledger_entry(leave_appln,from_date,leave_appln.from_date)
	cancel_attendance(from_date,leave_appln.to_date)
	leave_appln.publish_update()

def cancel_attendance(from_date,to_date):
	attendance = frappe.db.sql(
		"""select name from `tabAttendance` where (attendance_date between %s and %s) and docstatus < 2 and status in ('On Leave', 'Half Day')""",
		(from_date, to_date),
		as_dict=1,
	)
	for name in attendance:
		frappe.db.set_value("Attendance", name, "docstatus", 2)

def manage_leave_ledger_entry(leave_appln,from_date,appln_from_dt):
		expiry_date = get_allocation_expiry_for_cf_leaves(
			leave_appln.employee, leave_appln.leave_type, from_date, appln_from_dt
		)
		lwp = frappe.db.get_value("Leave Type", leave_appln.leave_type, "is_lwp")
		if expiry_date:
			leave_appln.create_ledger_entry_for_intermediate_allocation_expiry(expiry_date, False, lwp)
		else:
			alloc_on_from_date, alloc_on_to_date = get_allocation_based_on_application_dates(leave_appln,appln_from_dt,from_date)
			if leave_appln.is_separate_ledger_entry_required(alloc_on_from_date, alloc_on_to_date):
				leave_appln.create_separate_ledger_entries(alloc_on_from_date, alloc_on_to_date, False, lwp)
			else:
				raise_exception = False if frappe.flags.in_patch else True
				total_leave_days = get_number_of_leave_days(
					leave_appln.employee, leave_appln.leave_type, appln_from_dt,from_date
				)
				args = dict(
					leaves=total_leave_days * -1,
					from_date=appln_from_dt,
					to_date=from_date,
					is_lwp=lwp,
					holiday_list=get_holiday_list_for_employee(leave_appln.employee, raise_exception=raise_exception)
					or "",
				)
				create_leave_ledger_entry(leave_appln, args)

def get_allocation_based_on_application_dates(leave_appln,from_date,to_date) -> tuple[dict, dict]:
		"""Returns allocation name, from and to dates for application dates"""

		def _get_leave_allocation_record(date):
			LeaveAllocation = frappe.qb.DocType("Leave Allocation")
			allocation = (
				frappe.qb.from_(LeaveAllocation)
				.select(LeaveAllocation.name, LeaveAllocation.from_date, LeaveAllocation.to_date)
				.where(
					(LeaveAllocation.employee == leave_appln.employee)
					& (LeaveAllocation.leave_type == leave_appln.leave_type)
					& (LeaveAllocation.docstatus == 1)
					& ((date >= LeaveAllocation.from_date) & (date <= LeaveAllocation.to_date))
				)
			).run(as_dict=True)

			return allocation and allocation[0]

		allocation_based_on_from_date = _get_leave_allocation_record(from_date)
		allocation_based_on_to_date = _get_leave_allocation_record(to_date)

		return allocation_based_on_from_date, allocation_based_on_to_date


def create_leave_ledger_entry(ref_doc, args):
	ledger = frappe._dict(
		doctype="Leave Ledger Entry",
		employee=ref_doc.employee,
		employee_name=ref_doc.employee_name,
		leave_type=ref_doc.leave_type,
		transaction_type=ref_doc.doctype,
		transaction_name=ref_doc.name,
		is_carry_forward=0,
		is_expired=0,
		is_lwp=0,
	)
	ledger.update(args)

	frappe.db.sql(
		"""DELETE
		FROM `tabLeave Ledger Entry`
		WHERE
			`transaction_name`=%s""",
		(ledger.transaction_name),
	)

	doc = frappe.get_doc(ledger)
	doc.flags.ignore_permissions = 1
	doc.submit()

	frappe.db.set_value("Leave Application",ref_doc.name,"custom_early_joining_date",doc.to_date)
	frappe.db.set_value("Leave Application",ref_doc.name,"custom_updated_total_leave_days",abs(doc.leaves))