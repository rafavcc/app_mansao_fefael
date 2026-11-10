from app.database import get_session, init_db
from app.crud import (
    create_regular_category, create_user, create_variable_category,
    get_regular_categories, get_users, get_variable_categories,
)

VARIABLE_CATEGORIES = sorted(
    (
    "Carro",     # car-related (gas, maintenance, parking)
    "Casa",      # home supplies
    "Comida",    # groceries and food
    "Outros",
    "Lazer",     # leisure / fun
    "Presentes",
    "Faxina",    # cleaning services
    "Gasolina",  # fuel
    "Taxi",      # rideshare / taxis
    "Tomtom",    # nosso tomtomzinho
    "Bacana",    # treats / nice things
    "Viagem",    # travel
    )
)

REGULAR_CATEGORIES = sorted(
    (
    "Aluguel",           # rent
    "Internet",          # internet bill
    "Condominio",        # condominium fee
    "Cemig",             # public electricity bill
    "Consorcio-MG",      # private electricity bill
    "IPTU",              # property tax
    "Cartao"             # Credit Card
    )
)

def seed():
    init_db() # Initiate the DB

    with get_session() as db:
        existing_users = {u.name for u in get_users(db)}
        if "FAFA" not in existing_users:
            create_user(db, name = "FAFA", full_name = "Rafael Viegas")
        if "FEFE" not in existing_users:
            create_user(db, name = "FEFE", full_name = "Fernanda Lages")
        print('Users Seeded')

        # Seed Variable Categories
        existing_var = {c.name for c in get_variable_categories(db)}
        for name in VARIABLE_CATEGORIES:
            if name not in existing_var:
                create_variable_category(db, name)
        print(f"✓ {len(VARIABLE_CATEGORIES)} variable categories seeded")

        # Seed Regular Categories
        existing_reg = {c.name for c in get_regular_categories(db)}
        for name in REGULAR_CATEGORIES:
            if name not in existing_reg:
                create_regular_category(db, name)
        print(f"✓ {len(REGULAR_CATEGORIES)} regular categories seeded")

    print("\nDatabase seeded successfully!")

if __name__ == "__main__":
    seed()
