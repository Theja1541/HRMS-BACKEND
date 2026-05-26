def is_payroll_closed(*args, **kwargs):
    from .payroll_helpers import is_payroll_closed as _is_payroll_closed

    return _is_payroll_closed(*args, **kwargs)


def is_super_admin(*args, **kwargs):
    from .payroll_helpers import is_super_admin as _is_super_admin

    return _is_super_admin(*args, **kwargs)


def get_current_salary(*args, **kwargs):
    from .salary_utils import get_current_salary as _get_current_salary

    return _get_current_salary(*args, **kwargs)