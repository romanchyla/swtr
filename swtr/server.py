# -*- coding: utf-8 -*-

from flask import Flask, session, request, make_response, url_for, redirect,\
    render_template, jsonify, abort
from logging import FileHandler
from datetime import datetime, timedelta
import lxml.html
from urllib import quote_plus
import requests
import json
import StringIO
import imghdr
import config
import logging
import os


app = Flask(__name__)
app.config['SECRET_KEY'] = config.secret_key

# Setup error logging for the application.
if not os.path.exists(os.path.join(os.path.dirname(__file__),'logs/')):
    """ Create the directory if not exists"""
    os.makedirs(os.path.join(os.path.dirname(__file__),'logs/'), mode=0744)
fil = FileHandler(os.path.join(os.path.dirname(__file__), 'logs/', 'logme'), mode='a')
fil.setLevel(logging.ERROR)
app.logger.addHandler(fil)


@app.route('/', methods=['GET'])
def index():

    # if auth_tok is in session already..
    if 'auth_tok' in session:
        auth_tok = session['auth_tok']

        # check if it has expired
        oauth_token_expires_in_endpoint = config.swtstoreURL +\
            '/oauth/token-expires-in'
        resp = requests.get(oauth_token_expires_in_endpoint)
        expires_in = json.loads(resp.text)['expires_in']

        # added for backwared compatibility. previous session stores did not
        # have issued key
        try:
            check = datetime.utcnow() - auth_tok['issued']

            if check > timedelta(seconds=expires_in):
                # TODO: try to refresh the token before signing out the user
                auth_tok = {'access_token': '', 'refresh_token': ''}
            else:
                """access token did not expire"""
                pass

        # if issued key is not there, reset the session
        except KeyError:
            auth_tok = {'access_token': '', 'refresh_token': ''}

    else:
        auth_tok = {'access_token': '', 'refresh_token': ''}

    #print 'existing tokens'
    #print auth_tok
    payload = {'what': 'img-anno',
               'access_token': auth_tok['access_token']}
    req = requests.get(config.swtstoreURL + '/api/sweets/q', params=payload)
    sweets = req.json()
    return render_template('index.html', access_token=auth_tok['access_token'],
                           refresh_token=auth_tok['refresh_token'],
                           config=config, url=request.args.get('where'),
                           bookmark=quote_plus(config.app_url), sweets=sweets)


@app.route('/authenticate', methods=['GET'])
def authenticateWithOAuth():
    auth_tok = None
    code = request.args.get('code')

    # prepare the payload
    payload = {
        'scopes': 'email sweet',
        'client_secret': config.app_secret,
        'code': code,
        'redirect_uri': config.redirect_uri,
        'grant_type': 'authorization_code',
        'client_id': config.app_id
    }

    # token exchange endpoint
    oauth_token_x_endpoint = config.swtstoreURL + '/oauth/token'
    resp = requests.post(oauth_token_x_endpoint, data=payload)
    auth_tok = json.loads(resp.text)

    if 'error' in auth_tok:
        return make_response(auth_tok['error'], 200)

    # set sessions etc
    session['auth_tok'] = auth_tok
    session['auth_tok']['issued'] = datetime.utcnow()
    return redirect(url_for('index'))


# endpoint to search the Open Cuultur Data APIs
# takes in `query`, `size`, and `from` parameters in query string
# returns a JSON response
@app.route('/search/ocd', methods=['GET'])
def searchOCD():
    query = request.args.get('query')
    #collection = flask.request.args.get('collection')
    size = request.args.get('size') or 9
    offset = request.args.get('from') or 0

    # if query parameter is not passed, return bad request.
    if not query:
        abort(400)

    payload = {
        'query': query,
        'facets': {
            'collection': {},
            'date': {'interval': 'day'}
        },
        'filters': {
            'media_content_type': {'terms': ['image/jpeg', 'image/png']}
        },
        'size': size,
        'from': offset
    }
    resp = requests.post('http://api.opencultuurdata.nl/v0/search',
                         data=json.dumps(payload))

    response = make_response()
    response.data = json.dumps(resp.json())
    response.headers['Content-type'] = 'application/json'
    return response


# resolve OCD Media URLs: http://docs.opencultuurdata.nl/user/api.html#resolver
@app.route('/resolve-ocd-media', methods=['GET'])
def resolveOCDMediaURLs():

    media_hash = request.args.get('hash') or None

    if not media_hash:
        abort(400)

    resp = requests.get('http://api.opencultuurdata.nl/v0/resolve/' +
                        media_hash)

    return jsonify(url=resp.url)


@app.route('/media-type', methods=['GET'])
def getMediaType():

    where = request.args.get('where') or None

    if not where:
        abort(400)

    resp = requests.get(where)
    content = resp.text

    if imghdr.what('ignore', content) is None:
        return jsonify({'type': 'html'})
    else:
        return jsonify({'type': 'image'})


@app.route('/webpage', methods=['GET'])
def annotate_webpage():

    where = request.args.get('where')
    # add extra headers and hope that content based on IPs can get served
    # correctly
    # ex: google, youtube serving the right page from where the client
    # requested and not where this code is hosted
    headers = {
        'X-Forwarded-For': request.remote_addr,
        'Accept-Language': request.headers.get('Accept-Language')
    }

    response = requests.get(where, headers=headers)
    content = response.text

    if imghdr.what('ignore', content) is None:
        response = make_response()
        try:
            root = lxml.html.parse(StringIO.StringIO(content)).getroot()
        except Exception, e:
            response.data = 'The webpage you requested has some errors, so it\
                          cannot be displayed. Sorry for the inconvenience.'
            return response

        root.make_links_absolute(where,
                                 resolve_base_href=True)

        # rewrite all the links of the page to redirect via this endpoint
        # so that they become swtr browsable.
        #root.rewrite_links(relocate_href, resolve_base_href=True)
        for elem, attr, link, pos in root.iterlinks():
            if elem.tag == 'a' and attr == 'href':
                # url encode the link; and encode it utf-8 anyway to handle
                # links in other characters
                target = quote_plus(link.encode('utf-8'))
                new_link = '{0}/webpage?where={1}'.format(config.app_url,
                                                          target)
                elem.set('href', new_link)

        # inject the required JS + CSS for annotating the webpage
        addScript('//code.jquery.com/jquery-1.11.0.min.js', root)
        #addScript(url_for('static', filename='js/lib/showdown.js'), root)
        addScript(url_for('static', filename='js/annotator-full.min.js'),
                  root)
        #addScript(url_for('static',
        #          filename="js/annotorious.okfn.0.3.js"),
        #          root)
        addScript(url_for('static', filename='js/txt_swtr.js'), root)
        addCSS(url_for('static', filename='css/annotator.min.css'), root)

        response.data = lxml.html.tostring(root)
        return response


@app.route('/annotate', methods=['GET'])
def annotate():
    # img = urllib2.urlopen(flask.request.args['where']).read()
    where = request.args.get('where')
    response = requests.get(where)
    content = response.text
    if imghdr.what('ignore', content) is None:
        root = lxml.html.parse(StringIO.StringIO(content)).getroot()
        root.make_links_absolute(where,
                                 resolve_base_href=True)

        addScript("//code.jquery.com/jquery-1.11.0.min.js", root)
        addScript(url_for('static', filename="js/annotator-full.min.js"),
                  root)

        addCSS(url_for('static', filename='css/annotator.min.css'), root)
        addCSS(url_for('static', filename='css/swtmaker.css'), root)
        addCSS(url_for('static', filename='css/bootstrap.min.css'), root)
        addScript(url_for('static',
                          filename="js/lib/underscore-1.5.2.min.js"),
                  root)
        addScript(url_for('static',
                          filename="js/lib/backbone-1.0.0.min.js"),
                  root)
        addCSS(url_for('static', filename='css/annotorious.css'), root)
        addScript(url_for('static',
                          filename="js/annotorious.okfn.0.3.js"),
                  root)

        if 'auth_tok' in session:
            auth_tok = session['auth_tok']
        else:
            auth_tok = {'access_token': '', 'refresh_token': ''}

        configScript = root.makeelement('script')
        root.body.append(configScript)
        configScript.text = """window.swtr = window.swtr || {};
        swtr.swtstoreURL = {}
        swtr.endpoints = {}
        'get': '/api/sweets/q',
        'post': '/api/sweets',
        'auth': '/oauth/authorize',
        'login': '/auth/login',
        'logout': '/auth/logout'
        {};

        swtr.access_token = '{}';
        swtr.refresh_token = '{}';
        swtr.app_id = '{}';swtr.app_secret = '{}';
        swtr.oauth_redirect_uri = '{}';""".format(
            '{}', 'function() {}return "{}"{}'.format('{',
                                                      config.swtstoreURL, '};'),
            '{', '}', auth_tok['access_token'], auth_tok['refresh_token'],
            config.app_id, config.app_secret,
            config.redirect_uri)
        configScript.set("type", "text/javascript")

        addScript(url_for('static', filename="js/oauth.js"), root)

        addScript(url_for('static', filename="js/app.js"), root)

        response = make_response()
        response.data = lxml.html.tostring(root)
        return response

    else:
        if 'auth_tok' in session:
            auth_tok = session['auth_tok']
        else:
            auth_tok = {'access_token': '', 'refresh_token': ''}

        return render_template('index.html',
                               access_token=auth_tok['access_token'],
                               refresh_token=auth_tok['refresh_token'],
                               config=config,
                               url=request.args.get('where'))


def addScript(src, el):
    script = el.makeelement('script')
    el.body.append(script)
    script.set("src", src)
    script.set("type", "text/javascript")


def addCSS(src, el):
    style = el.makeelement('link')
    el.body.append(style)
    style.set("href", src)
    style.set("rel", "stylesheet")
    style.set("type", "text/css")



# if the app is run directly from command-line
# assume its being run locally in a dev environment
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)