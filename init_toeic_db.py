from database import engine, Base
import models

def init_db():
    print("Initializing TOEIC LC tables...")
    Base.metadata.create_all(bind=engine)
    print("Done!")

if __name__ == "__main__":
    init_db()
