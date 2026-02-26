# from django.urls import path
# from .views import (
#     accounts_root,
#     login_view,
#     user_list,
#     employee_profile,
#     create_user,
#     update_user_role,
#     delete_user,
#     superadmin_analytics,
#     change_password,
# )

# urlpatterns = [
#     path("", accounts_root, name="accounts-root"),
#     path("login/", login_view, name="login"),

#     path("users/", user_list, name="user-list"),
#     path("users/create/", create_user, name="create-user"),
#     path("users/<int:user_id>/role/", update_user_role, name="update-role"),
#     path("users/<int:user_id>/delete/", delete_user, name="delete-user"),

#     path("profile/", employee_profile, name="employee-profile"),
#     path("analytics/", superadmin_analytics, name="analytics"),
#     path("change-password/", change_password, name="change-password"),
# ]

from django.urls import path
from .views import (
    accounts_root,
    login_view,
    superadmin_user_list,
    admin_user_list,
    hr_user_list,
    employee_profile,
    create_user,
    update_user_role,
    delete_user,
    superadmin_analytics,
    change_password,
)


urlpatterns = [
    path("", accounts_root, name="accounts-root"),
    path("login/", login_view, name="login"),

    # path("users/", user_list, name="user-list"),
    path("users/superadmin/", superadmin_user_list),
    path("users/admin/", admin_user_list),
    path("users/hr/", hr_user_list),
    path("users/create/", create_user, name="create-user"),
    path("users/<int:user_id>/role/", update_user_role, name="update-role"),
    path("users/<int:user_id>/delete/", delete_user, name="delete-user"),

    path("profile/", employee_profile, name="employee-profile"),
    path("analytics/", superadmin_analytics, name="analytics"),
    path("change-password/", change_password, name="change-password"),
    
]