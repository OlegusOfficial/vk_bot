import re
from config import FLIGHTS
from datetime import datetime, date, timedelta

from generate_ticket import generate_ticket

re_city = re.compile(r'москва|пекин|париж|лондон')
re_date = re.compile(r'(0[1-9]|[12][0-9]|3[01])-(0[1-9]|1[012])-(20)\d\d')
re_final = re.compile(r'[Дд]а|[Нн]ет')
re_phone_number = re.compile(r'^((8|\+7)[\- ]?)?(\(?\d{3}\)?[\- ]?)?[\d\- ]{7,10}$')
re_email = re.compile(r'^([a-z0-9_-]+\.)*[a-z0-9_-]+@[a-z0-9_-]+(\.[a-z0-9_-]+)*\.[a-z]{2,6}$')


def dispatcher(user_date, context):
    flights_list_to_write = []
    values_list = []
    min_days_value = None
    min_days = 31
    user_date_new = user_date
    for i in range(5):
        for value in FLIGHTS[context['departure']][context['arrival']]:
            if (0 <= int(value[0]) - user_date_new.day < min_days) and (value not in values_list):
                min_days = int(value[0]) - user_date_new.day
                min_days_value = value
        if min_days_value is None:
            min_days_value = FLIGHTS[context['departure']][context['arrival']][0]
            min_days = 0
            if user_date_new.month == 12:
                user_date_new = date(year=user_date_new.year + 1, month=1,
                                     day=int(min_days_value[0]))
            else:
                user_date_new = date(year=user_date_new.year, month=user_date_new.month + 1, day=int(min_days_value[0]))
        values_list.append(min_days_value)
        user_date_new += timedelta(days=min_days)
        flights_list_to_write.append([user_date_new.strftime("%d-%m-%Y"), min_days_value[1]])
        min_days = 31
        min_days_value = None
    result = []
    for value in flights_list_to_write:
        result.append(' '.join(value))
    return result


def handle_departure_city(text, context):
    match = re.match(re_city, text.lower())
    if match:
        context['departure'] = text.lower()
        return 1
    else:
        return 0


def handle_arrival_city(text, context):
    context['cities'] = '\n'.join([city for city in FLIGHTS.keys() if city != context['departure']])
    match = re.match(re_city, text.lower())
    if match:
        if FLIGHTS[context['departure']].get(text.lower()):
            context['arrival'] = text.lower()
            return 1
        else:
            return -1
    else:
        return 0


def handle_date(text, context):
    match = re.match(re_date, text)
    if match:
        user_date = datetime.strptime(text, '%d-%m-%Y')
        if user_date >= datetime.now():
            context['date'] = user_date.strftime("%H:%M %d-%m-%Y")
            context['flights'] = dispatcher(user_date, context)
            context['flights_to_write'] = '\n'.join(context['flights'])
            return 1
        else:
            return 0
    else:
        return 0


def handle_flight(text, context):
    try:
        if 0 < int(text) <= 5:
            context['flight'] = context['flights'][int(text) - 1]
            return 1
        else:
            return 0
    except:
        return 0


def handle_sits(text, context):
    try:
        if 0 < int(text) <= 5:
            context['sits'] = text
            return 1
        else:
            return 0
    except:
        return 0


def handle_comment(text, context):
    context['comment'] = text
    return 1


def handle_final(text, context):
    match = re.match(re_final, text)
    if match:
        if text == 'Да' or text == 'да':
            return 1
        else:
            return -1
    else:
        return 0


def handle_email(text, context):
    match = re.match(re_email, text)
    if match:
        context['email'] = text
        return 1
    else:
        return 0


def handle_phone_number(text, context):
    match = re.match(re_phone_number, text)
    if match:
        context['phone_number'] = text
        return 1
    else:
        return 0


def generate_ticket_handler(context):
    return generate_ticket(fio=context['user_name'], from_=context['departure'], to=context['arrival'],
                           flight=context['flight'], email=context['email'])
