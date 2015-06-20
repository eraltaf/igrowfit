__author__ = 'Shang Liang'
from collections import OrderedDict

DB_NAME = 'igrowfit'
SECRET_KEY = 'b8W2[BTU\/36465=9b5>1{%ZNn5e7b'
SECURITY_LOGIN_USER_TEMPLATE = 'login.html'
SECURITY_PASSWORD_HASH = 'sha512_crypt'
SECURITY_PASSWORD_SALT = 'vnwg518q^-0$W08<9732330uy\JzN'
CATEGORIES = OrderedDict([
	('yoga', 'Yoga'),
    ('pilates', 'Pilates'),
    ('spinning','Spinning'),
    ('aerobics', 'Aerobics'),
    ('trx', 'TRX & Circuit Training'),
	('kickboxing', 'Kickboxing & Matial Arts'),
	('dance', 'Dance')])