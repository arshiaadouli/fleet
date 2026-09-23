import os
import sys
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError
# pip install pymongo python-dotenv

# .env lives next to this file, or next to the .exe in a PyInstaller build
BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

class FleetCardVal:
    def __init__(self):
        database = "shared"

        self.connection_url = os.getenv("MONGODB_URI")
        if not self.connection_url:
            raise RuntimeError(f"MONGODB_URI is not set. Add it to {os.path.join(BASE_DIR, '.env')} (see .env.example)")

        self.client = MongoClient(self.connection_url)
        self.db = self.client[database]
        self.collection = self.db["fleetcard"]

    def check_db_connection(self):
        """Check if the database connection is active."""
        try:
            self.client.admin.command("ping")
            print("Database connection successful!")
            return True
        except PyMongoError as e:
            print("Database connection failed:", e)
            return False

    def insert_from_pdf(self, card_number, fuel_type, type, rego, price, datetime, exp_month, exp_year):
        four_digit = card_number[-4:]
        try:
            print("Connected to the database.")

            existing = self.existing_trans(four_digit, fuel_type, rego)

            if existing:
                print("exists")
                existing_price = existing.get("price", 0)

                if price > existing_price:
                    self.collection.update_one(
                        {
                            "card_number": four_digit,
                            "fuel_type": fuel_type,
                            "rego": rego,
                        },
                        {
                            "$set": {
                                "price": price,
                                "datetime": datetime,
                                "exp_month": exp_month,
                                "exp_year": exp_year,
                                "full_card_number": card_number,
                            }
                        },
                    )
                    print("Data updated successfully. - price change")
                else:
                    self.collection.update_one(
                        {
                            "card_number": four_digit,
                            "fuel_type": fuel_type,
                            "rego": rego,
                        },
                        {
                            "$set": {
                                "datetime": datetime,
                                "exp_month": exp_month,
                                "exp_year": exp_year,
                                "full_card_number": card_number,
                            }
                        },
                    )
                    print("Data updated successfully. - exp change")
            else:
                self.collection.insert_one(
                    {
                        "card_number": four_digit,
                        "fuel_type": fuel_type,
                        "type": type,
                        "rego": rego,
                        "price": price,
                        "datetime": datetime,
                        "exp_month": exp_month,
                        "exp_year": exp_year,
                        "full_card_number": card_number,
                    }
                )
                print("Data inserted successfully. - insertion")

        except PyMongoError as e:
            print("Error while inserting into MongoDB:", str(e))

    def existing_trans(self, card_number, fuel_type, rego, datetime=None):
        """Check if a transaction already exists for this card_number (optionally filtered by datetime)."""
        try:
            query = {
                "card_number": card_number,
                "fuel_type": fuel_type,
                "rego": rego,
            }

            if datetime:
                query["datetime"] = datetime

            result = self.collection.find_one(query)

            if result:
                print("Transaction already exists:", result)
                return result
            else:
                print("No existing transaction found.")
                return None

        except PyMongoError as e:
            print("Error checking existing transaction:", str(e))
            return None

    def add_fleet_card(self, card_number, fuel_type, rego, datetime=None):
        """Check if a transaction already exists for this card_number (optionally filtered by datetime)."""
        try:
            query = {
                "card_number": card_number,
                "fuel_type": fuel_type,
                "rego": rego,
            }

            if datetime:
                query["datetime"] = datetime

            result = self.collection.find_one(query)

            if result:
                print("Transaction already exists:", result)
                return result
            else:
                print("No existing transaction found.")
                return None

        except PyMongoError as e:
            print("Error checking existing transaction:", str(e))
            return None

    def get_all(self):
        """Return all documents."""
        try:
            return list(self.collection.find())
        except PyMongoError as e:
            print("Error fetching all documents:", str(e))
            return None

    def get_filtered_rows(self):
        """
        Equivalent of:
        SELECT * FROM fleetcardval
        WHERE full_card_number != "" AND fuel_type != "Merchant Surcharge";
        """
        try:
            query = {
                "full_card_number": {"$ne": ""},
                "fuel_type": {"$ne": "Merchant Surcharge"},
            }
            return list(self.collection.find(query))
        except PyMongoError as e:
            print("Error fetching filtered rows:", str(e))
            return None


# usage
if __name__ == "__main__":
    db = FleetCardVal()
    rows = db.get_filtered_rows()
    print(rows)