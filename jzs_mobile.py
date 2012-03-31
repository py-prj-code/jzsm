# coding: utf-8

import pygeoip

from pymongo import Connection
from pymongo.objectid import ObjectId
from gevent.wsgi import WSGIServer
from flask import Flask, redirect, url_for, render_template, jsonify, \
        request, flash, abort


# config db
db = Connection('localhost', 27017).jzsou

# config app
app = Flask(__name__)
app.config.from_pyfile('config.cfg')

# consists
gic = pygeoip.GeoIP('/data/backup/GeoLiteCity.dat', pygeoip.MEMORY_CACHE)

CITIES = {
        'hangzhou': {'no': 1, 'label': 'hangzhou', 'name': u'杭州'},
        'shanghai': {'no': 2, 'label': 'shanghai', 'name': u'上海'},
        'nanjing': {'no': 3, 'label': 'nanjing', 'name': u'南京'},
        'beijing': {'no': 4, 'label': 'beijing', 'name': u'北京'},
        'shenzhen': {'no': 5, 'label': 'shenzhen', 'name': u'深圳'},
        'guangzhou': {'no': 6, 'label': 'guangzhou', 'name': u'广州'},
        }

CATES = {
        'banjia': {'no': 1, 'logo': 'move', 'label': 'banjia', 'name': u'搬家'},
        'jiadianweixiu': {'no': 2, 'logo': 'fix', 'label': 'jiadianweixiu', 'name': u'家电维修'},
        'kongtiaoyiji': {'no': 3, 'logo': 'fan', 'label': 'kongtiaoyiji', 'name': u'空调移机'},
        'guandaoshutong': {'no': 4, 'logo': 'pipe', 'label': 'guandaoshutong', 'name': u'管道疏通'},
        'kaisuo': {'no': 5, 'logo': 'unlock', 'label': 'kaisuo', 'name': u'开锁'},
        'yuesao': {'no': 6, 'logo': 'baby', 'label': 'yuesao', 'name': u'月嫂'},
        'zhongdiangong': {'no': 7, 'logo': 'clean', 'label': 'zhongdiangong', 'name': u'钟点工'},
        'xiudiannao': {'no': 8, 'logo': 'pc', 'label': 'xiudiannao', 'name': u'修电脑'},
        }

@app.errorhandler(404)
def page_not_found(error):
    return render_template("errors/404.html", error=error)

@app.errorhandler(500)
def server_error(error):
    return render_template("errors/500.html", error=error)


# request handlers
@app.route('/')
@app.route('/<city>/')
def home_list(city=None):
    if not city:
        city = get_city_by_ip()

    order_cates = sorted(CATES.values(), lambda e1, e2: e1['no'] - e2['no'])

    return render_template('home_list.html',
            cates=order_cates,
            city=CITIES[city])


@app.route('/entry/<city>/<cate>/cate')
@app.route('/entry/<city>/<q>/search')
def entry_list(city, cate=None, q=None):

    query_dict = {
            'city_label': city,
            'status': 'show',
            }

    args = {
            '_id': 1,
            'title': 1,
            'address': 1,
            }

    st = int(request.args.get('st', 1))

    # process functions
    if cate:
        query_dict['tags'] = cate

    if q:
        rqs = [e.lower() for e in re.split('\s+', q) if e]
        regex = re.compile(r'%s' % '|'.join(rqs), re.IGNORECASE)
        query_dict['$or'] = [{'title': regex}, {'brief': regex},
                {'desc': regex}, {'tags': {'$in': rqs}}] 

    cur_entry = db.Entry.find(query_dict, args)

    num = cur_entry.count()
    entries = list(cur_entry.skip(st).limit(20))

    for e in entries:
        e['pk'] = str(e['_id'])
        del e['_id']

    # what's next
    url = ''
    if st + 20 < num:
        if cate:
            url = url_for('search', city=city, st=st+20, q='tag:%s' % cate)

        if q:
            url = url_for('search', city=city, st=st+20, q='key:%s' % q)

    return render_template('entry_list.html',
            entries=entries,
            num=num,
            cate=cate and CATES[cate],
            data_url=url)


@app.route('/<city>/s/')
def search(city):

        query_dict = {
                'city_label': city,
                'status': 'show',
                }
        args = {
                '_id': 1,
                'title': 1,
                'address': 1,
                }

        pos = request.args.get('pos', None)
        if pos:
            lat, lon = pos.split(',')
            query_dict['_location'] = {
                    '$maxDistance': 0.091,
                    '$near': [float(lon), float(lat)]
                    }

        condition = request.args.get('q')
        if ':' in condition:
            field, value = condition.split(':')
        else:
            abort(400)

        st = int(request.args.get('st', 1))

        # process functions
        def do_tag(tag):
            query_dict['tags'] = tag
            return db.Entry.find(query_dict, args)

        def do_key(data):
            rqs = [e.lower() for e in re.split('\s+', data) if e]
            regex = re.compile(r'%s' % '|'.join(rqs), re.IGNORECASE)
            query_dict['$or'] = [{'title': regex}, {'brief': regex},
                    {'desc': regex}, {'tags': {'$in': rqs}}] 
            return db.Entry.find(query_dict, args)

        handle_q = {
                'tag': do_tag, 
                'key': do_key,
                }

        if field in handle_q:
            cur_entry = handle_q[field](value)
            num = cur_entry.count()
            entries = list(cur_entry.skip(st).limit(20))

            for e in entries:
                e['pk'] = str(e['_id'])
                del e['_id']

            # what's next
            if st + 20 < num:
                if pos:
                    next = url_for('search', city=city, q=condition, st=st+20, pos=pos)
                else:
                    next = url_for('search', city=city, q=condition, st=st+20)
            else:
                next = None

            return render_template('macros/_listcell.html',
                    entries=entries,
                    next=next)
        else:
            abort(400)


@app.route('/city/')
def change_city():
    city = get_city_by_ip()
    order_cities = sorted(CITIES.values(), lambda e1, e2: e1['no'] - e2['no'])

    return render_template('city.html',
            cur_city=CITIES[city],
            cities=order_cities,
            )


@app.route('/entry/<eid>/detail')
def detail(eid):
    entry = db.Entry.find_one({'_id': ObjectId(eid)})
    if not entry: abort(404)

    return render_template('detail.html',
            e=entry)


# helpers
def get_city_by_ip():
    ip = request.headers['X-Real-IP']
    city = 'hangzhou'
    if ip:
        record = gic.record_by_addr(ip)
        if record:
            city_ = record.get('city', None)
            if city_ and city_ in CITIES:
                city = city_.lower()
    return city

if __name__ == "__main__":
    http_server = WSGIServer(('127.0.0.1', 8300), app)
    http_server.serve_forever()
