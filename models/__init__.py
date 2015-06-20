__author__ = 'Shang Liang'

import types, json, config
import math
import socket
from os import path
from datetime import timedelta, datetime

from gridfs import GridFS
from flask.ext.mail import Mail, Message
from mongoengine import *
import mongoengine
from flask_login import current_user
from flask_security import UserMixin, RoleMixin, utils as security_utils
from flask import render_template, url_for


__all__ = ['User', 'Role', 'Studio', 'StudioStock', 'StudioClass', 'Schedule',
           'Package', 'StudioQuota', 'Subscription', 'Booking', 'send_feedback',
           'init_db']

mailer = Mail()


class User(Document, UserMixin):
    """
    Employees use nric as password
    """
    name = StringField(max_length=50, required=True)
    email = EmailField(unique=True)
    password = StringField()
    nric = StringField(max_length=20)
    contact = StringField(max_length=20)
    active = BooleanField(default=True)
    roles = ListField(ReferenceField('Role'), default=[])
    column_searchable_list = ('name', 'email')

    @property
    def entitled_studios(self):
        # sub = Subscription.objects(user=self).first()
        # if not sub:
        # return []
        # studio_quotas = StudioQuota.objects(package=sub.package, full=False)
        return [s for s in Studio.objects(active__ne=False)]

    @classmethod
    def studio_managers(cls):
        return User.objects(roles__name='Studio Manager')

    @classmethod
    def package_managers(cls):
        return User.objects(roles__name='HR Manager')

    def can_book(self):
        sub = Subscription.objects(user=self).first()
        if not (sub and sub.user.active):
            return 'You are not in any program at the moment.'

        total_bookings = Booking.objects(sub=sub,
                                         status__nin=['Rejected', 'Cancelled'])
        upcoming_bookings = Booking.objects(sub=sub,
                                            status__in=['Confirmed', 'Pending'])
        if len(upcoming_bookings) > sub.max_concurrent_booking:
            return 'You have reached your quota. You will be able to book more classes after attending your upcoming classes.'
        if len(total_bookings) >= sub.max_booking:
            return 'You have reached your maximum number of classes you can book.'
        if sub.package.is_empty:
            return 'Your company\'s program has reached its quota.'
        return 'True'

    def clean(self):
        if not isinstance(self._data['roles'], types.ListType):
            self._data['roles'] = [self._data['roles']]
        super(User, self).clean()

    def __unicode__(self):
        return self.name


class Role(Document, RoleMixin):
    """
    Default roles are created in "init_roles" functions
    System Admin, Package manager, Studio Manager, Employee
    """
    name = StringField(unique=True)
    description = StringField()

    def __unicode__(self):
        return self.name

    @classmethod
    def get_role(cls, name):
        return cls.objects(name=name).first()


class Studio(Document):
    name = StringField(max_length=100, unique=True)
    description = StringField()
    address = StringField()
    photo = ImageField()
    manager = ReferenceField('User')
    active = BooleanField(default=True)

    @property
    def photo_url(self):

        if self.photo.grid_id is None:
            return url_for('static', filename='upload/generic-logo.png')
        filename = str(self.photo.grid_id) + '.png'
        full_path = path.dirname(path.realpath(__file__)) + '/../static/upload/' + filename
        if not path.exists(full_path):
            fs = GridFS(mongoengine.connection.get_db('default'), 'images')
            data = fs.get(self.photo.grid_id)
            f = open(full_path, 'wb')
            f.write(data.read())
            f.close()
        return url_for('static', filename='upload/' + filename)

    def bookings(self, status):
        results = [b for b in Booking.objects() if b.schedule.studio == self]
        results = sorted(results, key=lambda bk: bk.schedule.start_time,
                         reverse=True)
        if status == 'All':
            return results
        if status == 'Today':
            return [b for b in results if b.schedule.start_time.strftime(
                '%m-%d-%Y') == datetime.now().strftime(
                '%m-%d-%Y') and b.status == 'Confirmed']
        elif status == 'Confirmed':
            return [b for b in results if
                    b.schedule.start_time - datetime.now() > timedelta(
                        days=1) and b.status == 'Confirmed']
        else:
            return [b for b in results if b.status == status]

    @property
    def active_quotas(self):
        quotas = StudioQuota.objects(studio=self)
        return [q for q in quotas if q.package.end_date >= datetime.now()]

    @property
    def expired_quotas(self):
        quotas = StudioQuota.objects(studio=self)
        return [q for q in quotas if q.package.end_date < datetime.now()]

    @property
    def stocks(self):
        return StudioStock.objects(studio=self).order_by('-id')

    def consolidate(self):
        stocks = StudioStock.objects(studio=self).order_by('start_date')
        bookings = [b for b in
                    Booking.objects(status__nin=['Rejected', 'Cancelled']) if
                    b.schedule.studio == self]
        for stock in stocks:
            tmp = [b for b in bookings if
                   b.schedule.start_time > stock.start_date and
                   b.schedule.end_time < stock.end_date]
            stock.used = len(tmp)
            stock.save()


    def __unicode__(self):
        return self.name


class StudioStock(Document):
    studio = ReferenceField('Studio')
    quantity = IntField()
    used = IntField(default=0)
    start_date = DateTimeField()
    end_date = DateTimeField()


class StudioClass(Document):
    name = StringField(max_length=100)
    studio = ReferenceField('Studio', required=True)
    description = StringField()
    category = StringField(max_length=30, choices=config.CATEGORIES.keys())
    tags = ListField(StringField(max_length=30))
    active = BooleanField(default=True)

    # CSV text of the schedule. This will be parsed and generate individual
    # schedules
    # Mon 12:00 13:30 5
    # Tue 13:00 14:30 5
    schedule = StringField()
    effective_date = DateTimeField()


    @classmethod
    def categories(cls):
        # TODO: If category is a list, will this work?
        StudioClass.objects().distinct('category')

    def generate_schedule(self, day):

        if self.effective_date and self.effective_date > day:
            return ''
        date = day.strftime('%a')
        for line in self.schedule.split("\n"):
            parts = line.split()
            if len(parts) < 4:
                return 'Error: %s %s %s <br/>' % (self.studio.name, self.name, line)
            if parts[0] == date:
                temp = parts[1].split(':')

                hh = int(temp[0])
                mm = int(temp[1])
                start_time = day.replace(hour=hh, minute=mm, second=0,
                                         microsecond=0)
                temp = parts[2].split(':')
                hh = int(temp[0])
                mm = int(temp[1])
                end_time = day.replace(hour=hh, minute=mm, second=0,
                                       microsecond=0)
                capacity = int(parts[3])
                s, created = Schedule.objects.get_or_create(studio_class=self,
                                                            start_time=start_time,
                                                            end_time=end_time,
                                                            studio=self.studio,
                                                            capacity=capacity)
                s.save()
        return ''

    def change_schedule(self, schedule, effective_date, force=False):
        schedules = Schedule.objects(studio_class=self, start_time__gt=effective_date)
        conflicts = Booking.objects(status__in=['Pending', 'Confirmed'], schedule__in=schedules)
        if len(conflicts) == 0 or force == True:
            schedules.delete()
            self.schedule = schedule
            self.effective_date = effective_date
            self.save()
            d = datetime.now()
        for x in xrange(0, 30):
            self.generate_schedule(d + timedelta(days=x))
        else:
            return json.dumps(
                [b.schedule.start_time.strftime('%Y-%m-%d, %H:%M') + ': ' + str(b.sub) for b in conflicts])

    def __unicode__(self):
        return self.name


class Schedule(Document):
    studio_class = ReferenceField('StudioClass')
    studio = ReferenceField('Studio')  # added for query convenience
    start_time = DateTimeField(unique_with=['studio_class'])
    end_time = DateTimeField()

    booked = IntField(default=0)
    capacity = IntField(default=0)
    full = BooleanField(default=False)

    def __unicode__(self):
        return self.start_time.strftime('%d-%m-%Y %H:%M') + ' ' + self.studio_class.name + ' ' + self.studio.name

    @classmethod
    def search(cls, keyword, date, time, region=None):
        """
        Search for classes
        :param keyword:
        :param date:
        :param time:
        :param region: Not used now
        :return: list of Schedules. 'home' if no search criteria is given.
        """
        if not (keyword or date or time):
            return 'home'

        classQuery = Q(active__ne=False)
        if keyword:
            classQuery &= Q(category__icontains=keyword) | Q(name__icontains=keyword)
            s = Studio.objects(name=keyword).first()
            if s:
                classQuery |= Q(studio=s)

        if current_user.is_authenticated():
            u = User.objects(id=current_user.id).first()
            sub = Subscription.objects(user=u).first()
            if sub:
                sq = StudioQuota.objects(package=sub.package)
                classQuery &= Q(studio__in=[s.studio for s in sq])

        query = Q(studio_class__in=StudioClass.objects(classQuery))

        if date:
            date = datetime.strptime(date, '%d-%m-%Y')
            if date - datetime.now() < timedelta(days=1):
                date = datetime.now() + timedelta(days=1)
            query &= Q(start_time__gte=date)
            query &= Q(start_time__lte=date + timedelta(days=1))
        else:
            query &= Q(start_time__gte=datetime.now() + timedelta(days=2))

        if time:
            results = list()
            for r in Schedule.objects(query):
                h1 = int(time[:time.find(':')])
                h2 = r.start_time.hour + r.start_time.minute / 60.0
                if math.fabs(h1 - h2) < 1:
                    results.append(r)
            return results
        results = [s for s in Schedule.objects(query)]
        exact_match = []
        if keyword:
            exact_match = [s for s in results if s.studio_class.name.lower() == keyword.lower()]
        if len(exact_match) > 0:
            return exact_match
        else:
            return results


    def consolidate(self):
        bookings = Booking.objects(schedule=self,
                                   status__in=['Pending', 'Confirmed'])
        self.booked = len(bookings)
        self.full = self.booked >= self.capacity
        self.save()

    @property
    def duration(self):
        td = self.end_time - self.start_time
        return int(td.seconds / 60)


class Booking(Document):
    sub = ReferenceField('Subscription')
    schedule = ReferenceField('Schedule')
    status = StringField(default='Pending', max_length=20,
                         choices=('Pending', 'Confirmed', 'Rejected', 'Attended', 'Absent', 'Cancelled', 'Unmarked'))
    created_time = DateTimeField(default=datetime.now())
    last_update = DateTimeField(default=datetime.now())
    reject_reason = StringField()

    @classmethod
    def create(cls, schedule, sub):

        b = Booking()
        b.schedule = schedule
        b.sub = sub

        err = b._can_proceed()
        if err:
            return err

        if not schedule.full:
            b.status = 'Confirmed'

        b.save()

        msg = Message(sender='NO-REPLY@igrowfit.com',
                      subject='[iGrowFit] New Booking Requires Your Attention')
        msg.recipients = [schedule.studio.manager.email]
        msg.html = render_template('booking_new_email.html', booking=b)
        try:
            mailer.send(msg)
        except socket.error as e:
            pass
        return {'result': 'Success', 'message': 'Your booking is recorded'}

    @classmethod
    def upcoming_bookings(cls, sub):

        q = Q(sub=sub)
        q &= Q(status='Pending') | Q(status='Confirmed')

        bookings=[b for b in Booking.objects(q) if b.schedule.start_time > datetime.now()]
        return bookings

    @classmethod
    def past_bookings(cls, sub):
        q = Q(sub=sub)
        q &= Q(status='Pending') | Q(status='Confirmed')
        return [b for b in Booking.objects(q) if
                b.schedule.start_time < datetime.now()]

    @classmethod
    def daily_cleanup(cls):

        # Attended or absent but never marked
        for b in Booking.objects(status='Confirmed'):
            if b.schedule.start_time < datetime.now():
                b.status = 'Unmarked'
                b.save()

        # Pending but never get confirmed before 1 day in advance
        for b in Booking.objects(status='Pending'):
            if b.schedule.start_time - datetime.now() < timedelta(days=1):
                b.reject('The studio failed to respond in time.')


    def can_cancel(self, ndays=2):
        return self.schedule.start_time - datetime.now() > timedelta(days=ndays)

    @property
    def is_today(self):
        return self.schedule.start_time.strftime(
            '%Y-%m-%d') == datetime.now().strftime('%Y-%m-%d')

    def confirm(self):
        success_msg = 'Thank you.<br/><br/>Please remember to mark the ' \
                      'attendance ' \
                      'on the day.'
        if self.status == 'Confirmed':
            return {'result': 'Success', 'message': success_msg}

        if self.status != 'Pending':
            return {'result': 'Error',
                    'message': 'Sorry, the booking is already confirmed or '
                               'rejected'}
        self.status = 'Confirmed'
        self.last_update = datetime.now()
        self.save()

        msg = Message(sender='NO-REPLY@igrowfit.com',
                      subject='[iGrowFit] Your booking is confirmed')
        msg.recipients = [self.sub.user.email]
        msg.html = render_template('booking_confirmed_email.html', booking=self)
        # try:
        mailer.send(msg)
        # except socket.error as e:
        # pass
        return {'result': 'Success', 'message': success_msg}

    def reject(self, reason):
        success_msg = 'The booking has been rejected successfully.'
        self.status = 'Rejected'
        self.reject_reason = reason
        self.last_update = datetime.now()
        self.save()

        msg = Message(sender='NO-REPLY@igrowfit.com',
                      subject='[iGrowFit] Your booking is rejected')
        msg.recipients = [self.sub.user.email]
        msg.html = render_template('booking_rejected_email.html', booking=self)
        try:
            mailer.send(msg)
        except socket.error as e:
            return {'result': 'Success', 'message': msg.html}
        return {'result': 'Success', 'message': success_msg}

    def cancel(self):
        success_msg = 'You have successfully cancelled your class.'
        self.status = 'Cancelled'
        self.last_update = datetime.now()
        self.save()

        msg = Message(sender='NO-REPLY@igrowfit.com',
                      subject='[iGrowFit] A Booking is Cancelled')
        msg.recipients = [self.schedule.studio.manager.email]
        msg.html = render_template('booking_cancelled_email.html', booking=self)

        try:
            mailer.send(msg)
        except socket.error as e:
            pass
        return {'result': 'Success', 'message': success_msg}

    def save(self, force_insert=False, validate=True, clean=True,
             write_concern=None, cascade=None, cascade_kwargs=None,
             _refs=None, **kwargs):
        self._consolidate_all()
        return super(Booking, self).save(force_insert, validate, clean,
                                         write_concern, cascade, cascade_kwargs,
                                         _refs,
                                         **kwargs)

    def _consolidate_all(self):
        self.schedule.studio.consolidate()
        self.sub.consolidate()
        self.schedule.consolidate()
        studio_quota = StudioQuota.objects(package=self.sub.package,
                                           studio=self.schedule.studio).first()
        studio_quota.consolidate()

    def _can_proceed(self):
        if not self.sub.user.can_book():
            return {'result': 'Error',
                    'message': 'You have reached your booking limit.'}
        quota = StudioQuota.objects(studio=self.schedule.studio,
                                    package=self.sub.package).first()
        if quota.full:
            return {'result': 'Error',
                    'message': 'Sorry, the studio is fully booked'}
        if self.schedule.full:
            return {'result': 'Error',
                    'message': 'The class is fully booked.'}

        return None


class Package(Document):
    name = StringField(max_length=50, unique=True)
    manager = ReferenceField('User')
    start_date = DateTimeField()
    end_date = DateTimeField()

    @property
    def is_empty(self):
        return len(StudioQuota.objects(package=self, full=False)) == 0

    @property
    def studio_quotas(self):
        return StudioQuota.objects(package=self)

    @property
    def users(self):
        temp = [sub.user for sub in Subscription.objects(package=self)]
        return temp

    @property
    def subs(self):
        query = Q(package=self)
        return Subscription.objects(query).order_by('-Attended')

    def __unicode__(self):
        return "%s (%s - %s)" % (
            self.name, self.start_date.strftime('%d/%m/%Y'),
            self.end_date.strftime('%d/%m/%Y'))


class StudioQuota(Document):
    package = ReferenceField('Package')
    studio = ReferenceField('Studio')
    quota = IntField(default=10)
    used = IntField(default=0)
    full = BooleanField(default=False)
    _bookings = None

    def bookings(self, status):
        print self.studio
        if not self._bookings:
            self._bookings = Booking.objects(sub__in=Subscription.objects(package=self.package),
                                             schedule__in=Schedule.objects(studio=self.studio))
        return [b for b in self._bookings if b.status == status]

    def consolidate(self):
        bookings = Booking.objects(sub__in=Subscription.objects(package=self.package),
                                   status__nin=['Rejected', 'Cancelled'])

        self.used = len([b for b in bookings if b.schedule.studio == self.studio])
        self.full = self.used == self.quota
        self.save()


class Subscription(Document):
    user = ReferenceField('User')
    package = ReferenceField('Package', required=True)
    max_concurrent_booking = IntField(default=1)
    max_booking = IntField(default=5)
    booked = IntField(default=0)
    attended = IntField(default=0)
    absent = IntField(default=0)
    cancelled = IntField(default=0)

    def consolidate(self):
        bookings = Booking.objects(sub=self, status__nin=['Rejected', 'Cancelled'])
        self.booked = len(bookings)
        self.attended = len(Booking.objects(sub=self, status='Attended'))
        self.absent = len(Booking.objects(sub=self, status='Absent'))
        self.cancelled = len(Booking.objects(sub=self, status='Cancelled'))
        self.save()

    def __unicode__(self):
        return self.user.name + '(' + self.package.name + ')'


def send_feedback(form_type, message, user):
    msg = Message(sender='NO-REPLY@igrowfit.com',
                  subject='[iGrowFit]' + form_type)
    msg.recipients = ['shang@wewearglasses.com']
    msg.html = '<ul>'
    msg.html += '<li><b>From: </b>' + user.name + '</li>'
    msg.html += '<li><b>Email: </b>' + user.email + '</li>'
    msg.html += '<li><b>Message: </b>' + message + '</li>'
    try:
        mailer.send(msg)
    except socket.error as e:
        return msg.html
    return {'result': 'Success', 'message': 'Success'}


def init_db(app):
    mailer.init_app(app)
    app.mailer = mailer

    return

    roles = ['System Admin', 'HR Manager', 'Studio Manager', 'Employee']
    for r in roles:
        role, created = Role.objects.get_or_create(name=r)
        role.save()

    studio, created = Studio.objects.get_or_create(name='Physical Abuse',
                                                   address='30 Prinsep Street '
                                                           'Income at '
                                                           'Prinsep, #03-01 '
                                                           'Singapore 188647')
    if created:
        studio.save()
        stock, created = StudioStock.objects.get_or_create(
            studio=Studio.objects().first(), quantity=100,
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=90))
        stock.save()

    emails = ['shang@wewearglasses.com', 'joy@igrow.sg',
              'valerie@wewearglasses.com', 'rupali@igrow.sg',
              'liang.shang@gmail.com']
    names = ['Shang Liang', 'Joy Koh', 'Valerie Loh', 'Rupali Ghorpade',
             'Xiao Hong']

    roles = [Role.objects().first(),
             Role.objects().first(),
             Role.objects()[1],
             Role.objects()[2],
             Role.objects()[3]]

    with app.app_context():
        password = security_utils.encrypt_password('password123')

    for i in xrange(0, len(emails)):
        u = User.objects(email=emails[i]).first()
        if not u:
            u = User(email=emails[i], name=names[i], password=password)
            u.roles = [roles[i]]
            u.save()
            if names[i] == 'Rupali Ghorpade':
                studio = Studio.objects().first()
                studio.manager = u
                studio.save()

    p, created = Package.objects().get_or_create(name='DBS')
    if created:
        p.manager = User.objects()[2]
        p.studio = Studio.objects().first()
        p.start_date = datetime.now()
        p.end_date = datetime.now() + timedelta(days=90)
        p.save()
        StudioQuota(package=p, studio=Studio.objects().first(), quota=50).save()

    sub, created = Subscription.objects().get_or_create(user=User.objects()[4],
                                                        package=p)
    if created:
        sub.max_concurrent = 2
        sub.max_total = 100
        sub.save()

    # classes = [
    #     ('Yoga', "Mon 12:20 13:25 5\nFri 18:30 19:25 5", 'yoga'),
    #     ('Kickboxing', "Thu 18:15 19:10 5\nFri 12:30 12:55 5", 'kickboxing'),
    #     ('Pilates',
    #      "Tue 19:30 20:25 5\nWed 18:30 19:25 5\nThu 12:30 13:25 5\nSat 11:30 "
    #      "12:25 5",
    #      'pilates'),
    #     ('Zumba',
    #      "Mon 19:00 20:25 5\nTue 12:00 12:55 5\nTue 18:30 19:25 5\nWed 19:30 "
    #      "20:25 5\nThu 13:30 14:25 5\nSat 13:30 14:25 5\nSun11:30 12:25 5",
    #      'dance')
    # ]

    # for c in classes:
    #     gc, created = StudioClass.objects().get_or_create(
    #         studio=Studio.objects().first(),
    #         name=c[0])
    #     gc.schedule = c[1]
    #     gc.category = c[2]
    #     gc.save()