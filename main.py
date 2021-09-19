from baby import app, db, sio

if __name__ == "__main__":
    db.create_all()
    print("http://127.0.0.1:5000/")
    sio.run(app)
