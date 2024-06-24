from pymongo import MongoClient
#TEST IF 
def get_database():
    try:
        client = MongoClient('mongodb://************/',
                             username='************',
                             password='************',
                             authSource='************')
        database = client['************']
        collection = database['sent_and_delivered']
        return collection
    except Exception as e:
        print(f"Error connecting to the database: {e}")
        return None

def transfer_records():
    collection = get_database()
    if collection is not None:
        try:
            archived_collection = collection.database['sent_database']
            for record in collection.find():
                if record['status_id'] == '0' and record['timestamp'] is None:
                    continue  # Skip archiving the record
                archived_collection.insert_one(record)
                collection.delete_one({'_id': record['_id']})  # Delete record from sent_and_delivered
            return True
        except Exception as e:
            print(f"Error archiving records: {e}")
    return False

def archived_records():
    collection = get_database()
    if collection is not None:
        try:
            collection = collection.database['sent_database']
            return collection
        except Exception as e:
            print(f"Error connecting to the database: {e}")
    return None
