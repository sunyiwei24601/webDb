#coding: utf8
import os
from flask import Flask, redirect, url_for, render_template, request, session, flash
from dbHandler import DbHandler, import_data_to_table
from sql import *
import pandas as pd
#from werkzeug.utils import secure_filename

app = Flask(__name__)

DEFAULT_SQL = SELECT_ALL_DATA_SQL

'''
def make_conn():
    if not hasattr(g, 'db'):
        g.db = DbHandler(DB_NAME)
    return g.db

@app.teardown_appcontext
def close_db(error):
    if hasattr(g, 'db'):
        g.db.close_db()
'''


def get_table_fields(sql):
    with DbHandler(DB_NAME) as db:
        db.execute_sql(sql)
        entry = db.get_one_record()
    return( entry.keys() if entry else [] )

@app.route('/')
@app.route('/index')
@app.route('/records/')
def index():
    headers = ["***** 登录后才可查看更多哦 *****"]
    allFields = []
    entries = []
    tables = []
    num = 0
    isLogin = False
    isRoot = False
    curUser = session.get('user', None)
    if curUser:
        isLogin = True
        isRoot = True if curUser=="root" else False
        tables = session['tables']
        with DbHandler(DB_NAME) as db:
            db.execute_sql(session['sql'] % tables[0])
            entries = db.get_all_records()
        session['sql'] = DEFAULT_SQL	# back to initial sql.
        num = len(entries)
        headers = entries[0].keys() if num else []
        entries = (tuple(entry) for entry in entries)
        sql = DEFAULT_SQL + ' limit 1;'
        allFields = get_table_fields(sql %tables[0])
    return render_template('records.html', headers=headers, allFields=allFields, isRoot=isRoot,
                        tables=tables, entries=entries, num=num, isLogin=isLogin, user=curUser)


@app.route('/tables/')
def switchTable():
    new_table = request.args.get('currentTable', None)
    tables = session.get('tables')
    tables.remove(new_table)
    tables.insert(0, new_table)
    session['tables'] = tables
    return redirect(url_for('index'))
  
    
def verify_user(uname, pword):
    with DbHandler(DB_NAME) as db:
        query_sql = SEARCH_USER_TABLE_SQL %(uname, pword)
        db.execute_sql(query_sql)
        tables = db.get_all_records()
        if tables and uname=='root':
            db.execute_sql(SEARCH_ALL_TABLES_SQL)
            tables = db.get_all_records()
            tables.append(('users', ))	# users table is only visible to root.
        if tables:
            tables = [tuple(t)[0] for t in tables]
        return list(set(tables))

@app.route('/login/', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    tables = verify_user(username, password)
    if tables:
        session['tables'] = tables	# record table(s) of current user can do.
        session['user'] = username
        session['sql'] = DEFAULT_SQL
    else:
        flash("无效的用户名或密码！")
    return redirect(url_for('index'))


@app.route('/logout/')
def logout():
    session.pop('user', None)
    session.pop('tables', None)
    session.pop('sql', None)
    return redirect(url_for('index'))


@app.route('/users/', methods=['POST'])
def userConfig():
    newPword = request.form["newPword"]
    if newPword:
        with DbHandler(DB_NAME) as db:
            curUser = session.get('user')
            update_sql = UPDATE_USER_PASSWORD_SQL %(newPword, curUser)
            db.execute_sql(update_sql)
        return redirect(url_for('logout'))
    return redirect(url_for('index'))
    
    
@app.route('/query/')
def query():
    fields = []
    where = []
    for k, v in request.args.items():
        if not v:
            continue
        if k.startswith('where'):
            where.append( k[5:]+'='+"'%s'" %v )
        else:
            fields.append(k)
    if fields:
        session['sql'] = "select {0} from %s".format(','.join(fields))
    if where:
        session['sql'] += " where {0}".format(' and '.join(where))
    return redirect(url_for('index'))


@app.route('/addCol/')
def addCol():
    column = request.args.get('newCol')
    if column:
        #g_all_fields.append(column)
        add_col_sql = ADD_COLUMN_SQL %(session['tables'][0], column)
        with DbHandler(DB_NAME) as db:
            db.execute_sql(add_col_sql)
    return redirect(url_for('index'))


@app.route('/dropCol/')
def dropCol():
    tables = session['tables']
    curTable = session['tables'][0]
    all_fields = get_table_fields(session['sql'] %curTable)
    if request.args.keys():
        for k in request.args:
            all_fields.remove(k)
        drop_col_sql = DELETE_COLUMN_SQL %(curTable, curTable, ','.join(all_fields))
        with DbHandler(DB_NAME) as db:
            db.cursor.executescript(drop_col_sql)	# execute multiple sqls at once.
    return redirect(url_for('index'))
    
    
@app.route('/addRow/')
def addRow():
    fields = []
    values = []
    for k, v in request.args.items():
        if v:
            fields.append(k)
            values.append(v)
    if fields:
        insert_sql = INSERT_DATA_SQL.format(session['tables'][0], ','.join(fields)) %("','".join(values))
        with DbHandler(DB_NAME) as db:
            db.execute_sql(insert_sql)
    return redirect(url_for('index'))


@app.route('/dropRow/')
def dropRow():
    condition = ''
    for k, v in request.args.items():
        if v:
            condition += " %s='%s' and" %(k, v)
    delete_sql = DELETE_DATA_SQL %session['tables'][0]
    if condition:
        delete_sql += " where %s;" %condition[:-3]	# strip 'and'
    with DbHandler(DB_NAME) as db:
        db.execute_sql(delete_sql)
    return redirect(url_for('index'))


@app.route('/updateData/')
def updateData():
    update_part = ''
    condition = ''
    for k, v in request.args.items():
        if v:
            if k.startswith('new'):
                update_part += "%s='%s'," %(k[3:], v)
            else:
                condition += " %s='%s' and" %(k[3:], v)
    if update_part:
        update_sql = UPDATE_DATA_SQL %(session['tables'][0], update_part[:-1]) # strip ','
        if condition:
            update_sql += ' where %s;' %condition[:-3]
        with DbHandler(DB_NAME) as db:
            db.execute_sql(update_sql)
    return redirect(url_for('index'))
    

@app.route('/importTable/', methods=['POST'])
def importTable():
    tname = request.form['tableName']
    fileobj = request.files['inputfile']
    if tname and fileobj.filename.endswith('.csv'):
        inputfile = 'tempXXX.csv'
        fileobj.save(inputfile)
        #在这里添加处理函数
        fileDataframe = pd.DataFrame.from_csv(inputfile)
        dffile = 'tempDfXXX.csv'
        fileDataframe.to_csv(dffile)
        
        
        
        
        import_data_to_table(tname, dffile)
        os.remove(inputfile)
        tables = session['tables']
        tables.append(tname)
        session['tables'] = list(set(tables))
    return redirect(url_for('index'))


@app.route('/dropTable/')
def dropTable():
    tables = session.get('tables', [])
    with DbHandler(DB_NAME) as db:
        for k in request.args:
            db.execute_sql(DROP_TABLE_SQL %k)
            db.execute_sql(DELETE_TABLE_RECORD_SQL %k)
            tables.remove(k)
    session['tables'] = tables
    return redirect(url_for('index'))
