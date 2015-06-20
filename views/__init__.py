from flask_mongoengine.wtf.fields import ModelSelectField

from flask.ext.admin.base import AdminIndexView

from flask.ext.admin.form.widgets import Select2Widget

from flask_admin.contrib.mongoengine import ModelView
from flask_admin.base import BaseView, expose
from wtforms.fields import PasswordField
from flask_security.utils import encrypt_password
from wtforms.fields.simple import TextAreaField

from flask_login import current_user
from flask import redirect, abort, request

from models import *
from datetime import datetime


__all__ = ['init_admin_views', 'HomeView']


class DisabledField(TextAreaField):
    def __call__(self, *args, **kwargs):
        kwargs.setdefault('readonly', True)
        return super(DisabledField, self).__call__(*args, **kwargs)


class RestrictedView(BaseView):
    def is_accessible(self):
        if not current_user.has_role('System Admin'):
            redirect('/login?next=/admin')
            return False
        else:
            return True

    def _handle_view(self, name, **kwargs):
        if not current_user.has_role('System Admin'):
            return redirect('/login?next=/admin')


class HomeView(AdminIndexView, RestrictedView):
    @expose('/')
    def index(self):
        return self.render(self._template, studios=Studio.objects())


class LogoutView(BaseView):
    @expose('/')
    def logout(self):
        return redirect('/logout')


class UserView(ModelView, RestrictedView):
    form_create_rules = (
        'name', 'email', 'password2', 'nric', 'contact', 'active', 'roles')
    form_edit_rules = form_create_rules
    form_excluded_columns = ('password')
    column_exclude_list = ('password')

    def __init__(self, **kwargs):
        super(UserView, self).__init__(User, **kwargs)

    def scaffold_form(self):
        form_class = super(UserView, self).scaffold_form()
        form_class.password2 = PasswordField('Password')
        form_class.roles = ModelSelectField('Role', queryset=Role.objects(),
                                            model=Role, widget=Select2Widget())
        return form_class

    def on_model_change(self, form, model, is_created):
        if len(model.password2):
            model.password = encrypt_password(form.password2.data)


class StudioView(ModelView, RestrictedView):
    def __init__(self, **kwargs):
        super(StudioView, self).__init__(Studio, **kwargs)

    def scaffold_form(self):
        form_class = super(StudioView, self).scaffold_form()
        form_class.manager = ModelSelectField('Manager', queryset=User.objects(roles=Role.get_role('Studio Manager')),
                                              model=User, widget=Select2Widget())
        return form_class


class PackageView(ModelView, RestrictedView):
    can_delete = False
    form_create_rules = ('name', 'manager', 'start_date', 'end_date')

    def __init__(self, **kwargs):
        super(PackageView, self).__init__(Package, **kwargs)

    def scaffold_form(self):
        form_class = super(PackageView, self).scaffold_form()
        form_class.manager = ModelSelectField('Manager', queryset=User.objects(roles=Role.get_role('HR Manager')),
                                              model=User, widget=Select2Widget())
        return form_class


class SubscriptionView(ModelView, RestrictedView):
    _create_template = 'admin/create_subscription.html'
    _edit_template = 'admin/edit_subscription.html'
    _form_edit_rules = ('user',)


    def __init__(self, **kargs):
        super(SubscriptionView, self).__init__(Subscription, **kargs)

    def _scaffold_form(self):
        form_class = super(SubscriptionView, self).scaffold_form()
        form_class.users = TextAreaField('Users')
        return form_class

    def _create_model(self, form):
        """
        Data sequence: email, name, nric(or employment id), monthly_quota
        :param form:
        :return:
        """
        p = Package.objects(id=form.package.raw_data[0]).first()
        for l in form.users.data.split("\n"):
            parts = l.split(",")
            if len(parts) < 4:
                continue

            u = User.objects(email=parts[0]).first()
            if u is None:
                u = User(email=parts[0])
                u.roles.append(Role.get_role('Employee'))
            u.name = parts[1]
            u.nric = parts[2]
            u.password = encrypt_password(u.nric)

            u.save()

            s, created = Subscription.objects.get_or_create(user=u, package=p)
            s.max_concurrent_booking = int(parts[3])
            s.max_booking = int(parts[4])
            s.save()

        return True


class StudioQuotaView(ModelView, RestrictedView):
    form_create_rules = (
        'package', 'studio', 'quota')

    def __init__(self, **kwargs):
        super(StudioQuotaView, self).__init__(StudioQuota, **kwargs)


class StudioStockView(ModelView, RestrictedView):
    def __init__(self, **kwargs):
        super(StudioStockView, self).__init__(StudioStock, **kwargs)


class ScheduleView(ModelView, RestrictedView):
    column_default_sort = 'start_time'

    def __init__(self, **kwargs):
        super(ScheduleView, self).__init__(Schedule, **kwargs)


class BookingView(ModelView, RestrictedView):
    can_delete = False

    def __init__(self, **kwargs):
        super(BookingView, self).__init__(Booking, **kwargs)


class StudioClassView(ModelView, RestrictedView):
    column_default_sort = 'name'
    form_excluded_columns = ('effective_date')
    column_exclude_list = ('effective_date')

    def get_edit_form(self):
        form = super(StudioClassView, self).get_edit_form()
        form.schedule = DisabledField('schedule')
        return form

    def __init__(self, **kwargs):
        super(StudioClassView, self).__init__(StudioClass, **kwargs)


class ChangeSchedueView(RestrictedView):
    @expose('/', methods=['POST', 'GET'])
    def index(self):
        classes = StudioClass.objects()
        if request.method == 'POST':
            cid = request.form.get('studio-class', '')
            effective_date = datetime.strptime(request.form.get('effective_date', datetime.now().strftime('%Y-%m-%d')),
                                               '%Y-%m-%d')
            if cid != '':
                c = StudioClass.objects(id=cid).first()
                conflicts = c.change_schedule(request.form.get('schedule'), effective_date)
        return self.render('admin/edit_schedule.html', classes=classes, time=datetime.now().strftime('%Y-%m-%d'))


def init_admin_views(admin):
    admin.add_view(StudioClassView(name='Classes'))
    # admin.add_view(ChangeSchedueView(name='Change Class Schedules',category="Studio Classes"))
    admin.add_view(ScheduleView(name='Class Schedules'))
    admin.add_view(BookingView(name='Bookings'))
    admin.add_view(PackageView(category='Manage Packages'))
    admin.add_view(StudioQuotaView(category='Manage Packages'))
    admin.add_view(SubscriptionView(category='Manage Packages'))
    admin.add_view(UserView(category='Others'))
    admin.add_view(StudioView(category='Others'))
    admin.add_view(StudioStockView(category='Others'))
    admin.add_view(LogoutView(name='Logout'))