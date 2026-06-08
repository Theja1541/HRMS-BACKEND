from django.urls import path
from .views import (
    accounts_root,
    login_view,
    superadmin_user_list,
    admin_user_list,
    hr_user_list,
    company_user_list,
    company_user_create,
    company_user_update,
    employee_profile,
    create_user,
    update_user_role,
    delete_user,
    superadmin_reset_password,
    superadmin_block_user,
    superadmin_unlock_user,
    superadmin_reset_attempts,
    superadmin_analytics,
    company_list,
    company_create,
    company_detail,
    company_update,
    company_logo,
    company_branding,
    company_branding_logo,
    company_delete,
    company_activate,
    company_hard_delete,
    company_stop_actions,
    company_mark_paid,
    custom_token_refresh,
    change_password,
    change_password_with_old,
    forgot_password,
    logout_view,
    company_smtp_settings,
    company_smtp_test,
)
from apps.superadmin.views import monthly_growth_analytics


urlpatterns = [
    path("", accounts_root, name="accounts-root"),
    path("login/", login_view, name="login"),
    path("token/refresh/", custom_token_refresh, name="token-refresh"),

    path("users/superadmin/", superadmin_user_list),
    path("users/admin/", admin_user_list),
    path("users/hr/", hr_user_list),
    path("company-users/", company_user_list),
    path("company-users/create/", company_user_create),
    path("company-users/<int:user_id>/update/", company_user_update, name="company-user-update"),
    path("users/create/", create_user, name="create-user"),
    path("users/<int:user_id>/role/", update_user_role, name="update-role"),
    path("users/<int:user_id>/delete/", delete_user, name="delete-user"),
    path("users/<int:user_id>/reset-password/", superadmin_reset_password, name="superadmin-reset-password"),
    path("users/<int:user_id>/block/", superadmin_block_user, name="superadmin-block-user"),
    path("users/<int:user_id>/unlock/", superadmin_unlock_user, name="superadmin-unlock-user"),
    path("users/<int:user_id>/reset-attempts/", superadmin_reset_attempts, name="superadmin-reset-attempts"),

    path("companies/", company_list),  # GET list
    path("companies/create/", company_create),  # POST create
    path("companies/<int:company_id>/", company_detail),  # GET one
    path("companies/<int:company_id>/update/", company_update),  # PATCH/PUT
    path("companies/<int:company_id>/logo/", company_logo),  # POST/DELETE logo
    path("companies/<int:company_id>/delete/", company_delete),  # DELETE (soft)
    path("companies/<int:company_id>/stop-actions/", company_stop_actions),
    path("companies/<int:company_id>/mark-paid/", company_mark_paid),
    path("company-branding/", company_branding),
    path("company-branding/logo/", company_branding_logo),

    path("companies/<int:company_id>/activate/", company_activate),  # POST activate
    path("companies/<int:company_id>/hard-delete/", company_hard_delete),  # DELETE permanent

    path("company/smtp/", company_smtp_settings, name="company-smtp-settings"),
    path("company/smtp/test-email/", company_smtp_test, name="company-smtp-test"),

    path("profile/", employee_profile, name="employee-profile"),
    path("analytics/", superadmin_analytics, name="analytics"),
    path("analytics/monthly-growth/", monthly_growth_analytics),
    path("change-password/", change_password, name="change-password"),
    path("change-password-with-old/", change_password_with_old, name="change-password-with-old"),
    path("forgot-password/", forgot_password, name="forgot-password"),
    path("logout/", logout_view, name="logout"),
]
