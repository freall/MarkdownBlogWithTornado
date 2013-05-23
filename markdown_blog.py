'''
Created on 2013-5-19

@author: F
'''
import os.path
import time
import json
import hashlib

import tornado.web
import tornado.options
import tornado.httpserver
import tornado.ioloop

import markdown
import pymongo

from tornado.options import define, options
define('port', default = 8000, help = 'Run on the given port', type = int)

class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        return self.get_secure_cookie('username', None)

class IndexHandler(tornado.web.RequestHandler):
    def get(self):
        posts = self.application.dbhandler.getAllPosts()
        self.render('index.html', page_title = self.application.bloginfo['title'], posts = posts)

class NewPostHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render('new.html', page_title = 'index')
        
    @tornado.web.authenticated
    def post(self):
        title = self.get_argument('title')
        content_md = self.get_argument('content')
        content_html = markdown.markdown(content_md)
        postid = self.application.dbhandler.savePost(title, content_md, content_html)
        self.redirect('/' + str(postid))

class PostHandler(BaseHandler):
    def get(self, postid):
        post = self.application.dbhandler.getPostById(int(postid))
        if not post:
            self.set_status(404, 'Not Find Post!')
        else: 
            self.render('post_page.html', page_title = post['title'], post = post)

class LoginHandler(BaseHandler):
    def get(self):
        self.render('login.html', page_title='Login')
        
    def post(self):
        username = self.get_argument('username', None)
        password = self.get_argument('password', None)
        password = _encryptPassword(password)
        if not username or not password:
            self.redirect('/login')
            return
        passstring = self.application.dbhandler.getPassStringByName(username)
        if not passstring or passstring != password:
            self.redirect('/login')
            return
        else:
            self.set_secure_cookie('username', username)
            self.redirect(self.get_argument('next', '/'))

class LogoutHandler(BaseHandler):
    def get(self):
        pass

class DBHandler(object):
    def __init__(self, host, port, dbname):
        conn = pymongo.Connection(host, 27017)
        self.db = conn[dbname]
        
    def savePost(self, title, content_md, content_html):
        maxid_item = self.db.posts.find().sort('postid', pymongo.DESCENDING).limit(1)[0]
        maxid = maxid_item['postid']
        newid = maxid + 1
        self.db.posts.insert({
            'postid': newid,
            'time': time.time(),
            'title': title,
            'content_md': content_md, 
            'content_html': content_html
        })
        return newid

    def getPostById(self, postid):
        doc = self.db.posts.find_one({'postid': postid})
        return doc

    def getAllPosts(self):
        return self.db.posts.find().sort('postid', pymongo.DESCENDING)
    
    def getPassStringByName(self, username):
        doc = self.db.users.find_one({'username': username})
        if doc:
            return doc['password']
        else:
            return None
        
    def getBlogInfo(self):
        doc = self.db.bloginfo.find()[0]
        del doc['_id']
        return doc

class Application(tornado.web.Application):
    def __init__(self):

        self.dbhandler = DBHandler("localhost", 27017, "MarkdownBlog")
        self.bloginfo = self.dbhandler.getBlogInfo()
        
        handlers = [
            (r'/', IndexHandler),
            (r'/new', NewPostHandler),
            (r'/(\d+)', PostHandler),
            (r'/login', LoginHandler),
            (r'/logout', LogoutHandler)
        ]
        
        settings = {
            'template_path': os.path.join(os.path.dirname(__file__), "templates"),
            'static_path': os.path.join(os.path.dirname(__file__), "static"),
            'auto_escape': None,
            'xsrf_cookies': True,
            'login_url': '/login',
            'cookie_secret': 'QCzIQX6ERyWLq7bsKKgxbeUUps8V/kxrj7dk5dAEXaI='
        }
        
        tornado.web.Application.__init__(self, handlers, **settings)

def _encryptPassword(password):
    return hashlib.new("md5", password.encode('utf8')).hexdigest()   

if __name__ == '__main__':
    tornado.options.parse_command_line()
    server = tornado.httpserver.HTTPServer(Application())
    server.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()