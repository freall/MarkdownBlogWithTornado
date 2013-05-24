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
define('port', default = 8000, help='Run on the given port', type=int)

class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        return self.get_secure_cookie('username', None)

class IndexHandler(tornado.web.RequestHandler):
    def get(self):
        articles = self.application.dbHandler.getAllArticles()
        self.render('index.html',
                    blogInfo=self.application.blogInfo,
                    page_title=self.application.blogInfo['title'],
                    articles=articles)

class AdminHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        articles = self.application.dbHandler.getAllArticles()
        self.render('admin.html', page_title=self.application.blogInfo['title'],
                    blogInfo=self.application.blogInfo,
                    articles=articles)

class DeleteHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self, articleID):
        pass


class NewArticleHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render('new.html', page_title='New Article', blogInfo=self.application.blogInfo,)
        
    @tornado.web.authenticated
    def post(self):
        title = self.get_argument('title')
        content_md = self.get_argument('content')
        content_html = markdown.markdown(content_md)
        article = {
            'title': title,
            'content_md': content_md,
            'content_html': content_html
        }
        articleID = self.application.dbHandler.saveArticle(article)
        self.redirect('/' + str(articleID))

class ArticlePageHandler(BaseHandler):
    def get(self, articleID):
        article = self.application.dbHandler.getArticleById(int(articleID))
        if not article:
            self.set_status(404, 'Not Find Article!')
        else: 
            self.render('article_page.html',
                        page_title=article['title'],
                        blogInfo=self.application.blogInfo,
                        article=article)

class EditArticleHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self, articleID):
        if articleID:
            article = self.application.dbHandler.getArticleById(int(articleID))
            if article:
                self.render('edit.html', page_title='Edit',
                            blogInfo=self.application.blogInfo,
                            article=article)
            else:
                self.set_status(404)

    def post(self, articleID):
        if not articleID:
            self.redirect('/')
        article = self.application.dbHandler.getArticleById(int(articleID))
        title = self.get_argument('title')
        content_md = self.get_argument('content')
        content_html = markdown.markdown(content_md)
        article = {
            'title': title,
            'content_md': content_md,
            'content_html': content_html
        }
        self.application.dbHandler.modifyArticleById(articleID, article)
        self.redirect('/' + str(articleID))

class LoginHandler(BaseHandler):
    def get(self):
        self.render('login.html', page_title='Login', blogInfo=self.application.blogInfo,)
        
    def post(self):
        username = self.get_argument('username', None)
        password = self.get_argument('password', None)
        password = _encryptPassword(password)
        if not username or not password:
            self.redirect('/login')
            return
        passString = self.application.dbHandler.getPassStringByName(username)
        if not passString or passString != password:
            self.redirect('/login')
            return
        else:
            self.set_secure_cookie('username', username)
            self.redirect(self.get_argument('next', '/'))

class LogoutHandler(BaseHandler):
    def get(self):
        pass

class DBHandler(object):
    def __init__(self, host, port, dbName):
        conn = pymongo.Connection(host, 27017)
        self.db = conn[dbName]
        
    def saveArticle(self, article):
        maxIdItem = self.db.posts.find().sort('postid', pymongo.DESCENDING).limit(1)[0]
        maxId = maxIdItem['postid']
        newId = maxId + 1
        self.db.posts.insert({
            'postid': newId,
            'time': time.time(),
            'title': article['title'],
            'content_md': article['content_md'],
            'content_html': article['content_html']
        })
        return newId

    def modifyArticleById(self, articleID, modifiedArticle):
        foundArticle = self.getArticleById(int(articleID))
        if not foundArticle:
            postid = self.saveArticle(modifiedArticle)
            return postid
        foundArticle['title'] = modifiedArticle['title']
        foundArticle['content_md'] = modifiedArticle['content_md']
        foundArticle['content_html'] = modifiedArticle['content_html']
        self.db.posts.save(foundArticle)


    def getArticleById(self, articleID):
        doc = self.db.posts.find_one({'postid': articleID})
        return doc

    def getAllArticles(self):
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

        self.dbHandler = DBHandler("localhost", 27017, "MarkdownBlog")
        self.blogInfo = self.dbHandler.getBlogInfo()
        
        handlers = [
            (r'/', IndexHandler),
            (r'/new', NewArticleHandler),
            (r'/(\d+)', ArticlePageHandler),
            (r'/edit/(\d+)', EditArticleHandler),
            (r'/delete/(\d+)', DeleteHandler),
            (r'/admin', AdminHandler),
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
