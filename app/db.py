import mysql.connector as sql


def create_connection(database):
    """Create Connection with database"""
    return sql.connect(
        host = 'localhost',
        user = 'root',
        password = 'ather2010',
        database = database,
        auth_plugin = 'mysql_native_password'
    )
