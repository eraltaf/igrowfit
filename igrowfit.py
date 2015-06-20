from datetime import datetime, timedelta
from collections import Counter
import json

from flask import Flask, request, redirect, url_for
from flask.ext.login import login_required, current_user
from flask.ext.security.forms import LoginForm
from flask.ext.security.decorators import roles_accepted
from flask.templating import render_template
from flask_bootstrap import Bootstrap
import mongoengine
from flask_admin import Admin
from flask_security import Security, MongoEngineUserDatastore, \
    utils as security_utils

from views import init_admin_views, HomeView
from models import *


app = Flask(__name__)
app.debug=True
app.config.from_pyfile('config.py')
mongoengine.connect(app.config['DB_NAME'])

Bootstrap(app)
security = Security(app, MongoEngineUserDatastore(mongoengine, User, Role))
admin = Admin(app, index_view=HomeView(), name='iGrowFit',
              base_template='admin/base_template.html')
init_admin_views(admin)


def igf_context():
    context = {
        'login_form': LoginForm()
    }
    if current_user.is_authenticated():
        u = User.objects(id=current_user.id).first()
        context['can_book'] = u.can_book()
        context['entitled_studios'] = u.entitled_studios
        context['user'] = u
    else:
        context['user'] = None
        context['can_book'] = 'Login'
        context['entitled_studios'] = Studio.objects()

    context['banner'] = _decide_banner([])
    context['categories'] = app.config['CATEGORIES'].items()
    context['classes'] = dict()
    classes = StudioClass.objects(active__ne=False)
    for k, v in app.config['CATEGORIES'].items():
        context['classes'][k] = set([c.name for c in classes if c.category == k])

    return context


app.context_processor(igf_context)


@app.route('/')
def home():
    if current_user.has_role('Studio Manager'):
        u = User.objects(id=current_user.id).first()
        s = Studio.objects(manager=u).first()
        return redirect(url_for('studio_view', studio_id=str(s.id)))

    if current_user.has_role('HR Manager'):
        u = User.objects(id=current_user.id).first()
        p = Package.objects(manager=u).first()
        return redirect(url_for('package_view', package_id=str(p.id)))

    if current_user.has_role('System Admin'):
        return redirect('/admin')

    results = Schedule.search(request.args.get('keyword'),
                              request.args.get('date'),
                              request.args.get('time'))
    return render_template('home.html', results=results,
                           banner=_decide_banner(results))


def _decide_banner(results):
    keyword = request.args.get('keyword')
    if keyword in app.config['CATEGORIES'].keys():
        return dict(image='header-' + keyword + '.jpg',
                    header=app.config['CATEGORIES'][keyword].upper(),
                    sub_header='The perfect fitness class is just a click away')
    elif type(results) is str or len(results) == 0:
        return dict(image='header-home.jpg', header='GROW FIT TODAY',
                    sub_header='The perfect fitness class is just a click away')
    else:
        c = Counter([s.studio_class.category for s in results])
        print c
        cat, n = c.most_common(1)[0]
        return dict(image='header-' + cat + '.jpg',
                    header=app.config['CATEGORIES'][cat].upper(),
                    sub_header='The perfect fitness class is just a click away')


@app.route('/book/<schedule_id>')
@roles_accepted('Employee', 'HR Manager')
def book(schedule_id):
    u = User.objects(id=current_user.id).first()
    sub = Subscription.objects(user=u).first()

    schedule = Schedule.objects(id=schedule_id).first()
    if schedule:
        return json.dumps(Booking.create(schedule, sub))
    else:
        return json.dumps(
            {'result': 'Error', 'message': 'Unable to find the class'})


@app.route('/cancel/<booking_id>')
@roles_accepted('Employee', 'HR Manager')
def cancel(booking_id):
    u = User.objects(id=current_user.id).first()
    sub = Subscription.objects(user=u).first()
    booking = Booking.objects(sub=sub, id=booking_id).first()
    if booking:
        return json.dumps(booking.cancel())
    else:
        return json.dump({'result': 'Error',
                          'message': 'Unable to find the specified booking.'})


@app.route('/dashboard')
@login_required
@roles_accepted('Employee', 'HR Manager')
def dashboard():
    u = User.objects(id=current_user.id).first()
    if current_user.has_role('HR Manager'):
        p = Package.objects(manager=u).first()
        return redirect(url_for('package_view', package_id=str(p.id)))
    sub = Subscription.objects(user=u).first()
    return render_template('dashboard.html',
                           bookings=Booking.upcoming_bookings(sub))


@app.route('/history')
@login_required
@roles_accepted('Employee', 'HR Manager')
def history():
    u = User.objects(id=current_user.id).first()
    sub = Subscription.objects(user=u).first()
    return render_template('history.html', bookings=Booking.past_bookings(sub))


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/faq')
def faq():
    return render_template('faq.html')


@app.route('/privacy')
def privacy():
    return render_template('privacy.html')


@app.route('/terms')
def terms():
    return render_template('terms.html')


@app.route('/contact/<form_type>', methods=['GET', 'POST'])
@login_required
def contact(form_type):
    if request.method == 'GET':
        return render_template('contact.html', type=form_type)
    else:
        message = request.form.get('message')
        u = User.objects(id=current_user.id).first()
        send_feedback(form_type, message, u)
        return render_template('contact.html', type=form_type,
                               result={'result': 'Success',
                                       'message': 'Thank you for your '
                                                  'feedback.'})


@app.route('/studio/<studio_id>')
@login_required
@roles_accepted('Studio Manager')
def studio_view(studio_id):
    u = User.objects(id=current_user.id).first()
    studio = Studio.objects(id=studio_id).first()
    if studio.manager != u:
        return 'Access denied'

    return render_template('studio.html', studio=studio)


@app.route('/package/<package_id>', methods=['POST', 'GET'])
@login_required
@roles_accepted('HR Manager')
def package_view(package_id):
    u = User.objects(id=current_user.id).first()
    package = Package.objects(id=package_id).first()
    start = int(request.args.get('start', 0))
    if package.manager != u:
        return 'Access denied'

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        nric = request.form.get('nric')
        e = User.objects(email=email).first()
        if e is not None:
            return 'User already exists'
        password = security_utils.encrypt_password(nric)
        e = User(name=name, email=email, password=password, nric=nric,
                 roles=[Role.get_role('Employee')])
        e.save()
        sub = Subscription.objects(package=package).first()
        nsub = Subscription(package=package, user=e,
                            max_concurrent_booking=sub.max_concurrent_booking,
                            max_boooking=sub.max_booking)
        nsub.save()
        return 'Success'

    return render_template('package.html', package=package, start=start,
                           pages=int(len(package.subs) / 50))


@app.route('/toggle-user/<user_id>')
@login_required
@roles_accepted('HR Manager')
def toggle_user(user_id):
    u = User.objects(id=current_user.id).first()
    package = Package.objects(manager=u).first()
    employee = User.objects(id=user_id).first()
    if package == Subscription.objects(user=employee).first().package:
        employee.active = not employee.active
        employee.save()

        return 'done'
    else:
        return 'Access Denied'


@app.route('/attend/<booking_id>')
@login_required
@roles_accepted('Studio Manager')
def attend_class(booking_id):
    u = User.objects(id=current_user.id).first()
    b = Booking.objects(id=booking_id).first()
    if b.schedule.studio.manager != u or b.status == 'Absent' or \
                            b.schedule.start_time - datetime.now() > timedelta(
                    days=1):
        return 'Access denied'
    b.status = 'Attended'
    b.save()
    return 'Success'


@app.route('/absent/<booking_id>')
@login_required
@roles_accepted('Studio Manager')
def absent_class(booking_id):
    u = User.objects(id=current_user.id).first()
    b = Booking.objects(id=booking_id).first()
    if b.schedule.studio.manager != u or b.status == 'Attended' or \
                            b.schedule.start_time - datetime.now() > timedelta(
                    days=1):
        return 'Access denied'
    b.status = 'Absent'
    b.save()
    return 'Success'


@app.route('/confirm/<bid>')
@login_required
@roles_accepted('Studio Manager', 'System Admin')
def confirm_booking(bid):
    b = Booking.objects(id=bid).first()
    return render_template('booking_confirm.html', result=b.confirm())


@app.route('/reject/<bid>', methods=['GET', 'POST'])
@login_required
@roles_accepted('Studio Manager', 'System Admin')
def reject_booking(bid):
    b = Booking.objects(id=bid).first()
    if request.method == 'GET':
        return render_template('booking_reject.html', booking=b)
    else:
        result = b.reject(request.form['reason'])
        return render_template('booking_reject.html', result=result)


@app.route('/gen-schedules')
def gen_schedules():
    errors = ''

    Schedule.objects(end_time__lt=datetime.now(), booked=0).delete()
    for c in StudioClass.objects(active__ne=False):
        d = datetime.now()
        for x in xrange(0, 30):
            errors += c.generate_schedule(d + timedelta(days=x))
    return 'done<br/>' + errors


@app.route('/daily-cleanup')
def daily_cleanup():
    Booking.daily_cleanup()

    for c in StudioClass.objects():
        d = datetime.now()
        c.generate_schedule(d + timedelta(days=30))
    return 'done'


@app.before_first_request
def init_app():
    init_db(app)


if __name__ == '__main__':
    app.run(port=8080, host='0.0.0.0', debug=True)
