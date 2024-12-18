frappe.ui.form.on('Leave Application', {
	refresh(frm) {
		if(frm.doc.docstatus == 1 && frm.doc.status == "Approved"){
		    frm.add_custom_button('Amend', () => {
		        let d = new frappe.ui.Dialog({
		            title : 'Amend application',
		            fields:[
		                {
		                    label: 'Early Joining Date',
                            fieldname: 'from_date',
                            fieldtype: 'Date',
                            default:frm.doc.to_date
		                }
    		          ],
    		          size: 'large',
    		          primary_action_label: 'Amend',
    		          primary_action(values) {
		          		if(values.from_date < frm.doc.from_date){
                            	frappe.throw("Early joining date can not be before leave application date")
                            }
                        if(values.from_date > frm.doc.to_date){
                        	frappe.throw("Early joining date can not be after to date")
                        }
						frappe.call({
							method:"leave_amendment.events.leave_amendment.amend_leaves",
							args:{
								application: frm.doc.name,
								from_date: values.from_date
							},
							callback: function(r){
								frappe.show_alert({message:__("Amending"), indicator:'orange'});
							}
						})
                      frappe.msgprint("Updated")
                      d.hide();
                      frm.reload_doc();
    		        }
		        });
		        d.show();
		    });
		}
	}
})