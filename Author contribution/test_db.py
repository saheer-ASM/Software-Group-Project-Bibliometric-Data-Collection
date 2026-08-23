from database import get_connection


try:

    conn = get_connection()

    print("Database connected successfully!")

    conn.close()


except Exception as e:

    print("Connection error:")
    print(e)