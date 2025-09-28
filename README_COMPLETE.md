from server_sqlite import app, init_database

if __name__ == '__main__':
    init_database()
    app.run()