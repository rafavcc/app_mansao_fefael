"""
Tests for API endpoints.
"""
import pytest


class TestHealthEndpoint:
    """Tests for health check endpoint."""
    
    def test_health_check(self, client):
        """Test that health endpoint returns OK."""
        response = client.get("/api/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestVariableCategoriesEndpoint:
    """Tests for variable categories endpoint."""
    
    def test_list_variable_categories(self, client):
        """Test listing all variable categories."""
        response = client.get("/api/variable-categories")
        
        assert response.status_code == 200
        categories = response.json()
        
        # Should have at least the seeded categories
        assert isinstance(categories, list)
        assert len(categories) > 0
    
    def test_variable_categories_contains_expected(self, client):
        """Test that expected categories are present."""
        response = client.get("/api/variable-categories")
        
        assert response.status_code == 200
        categories = response.json()
        
        # Check for some expected categories
        category_names = set(categories)
        expected = {"Comida", "Carro", "Lazer"}
        
        for cat in expected:
            assert cat in category_names


class TestRegularCategoriesEndpoint:
    """Tests for regular categories endpoint."""
    
    def test_list_regular_categories(self, client):
        """Test listing all regular categories."""
        response = client.get("/api/regular-categories")
        
        assert response.status_code == 200
        categories = response.json()
        
        assert isinstance(categories, list)
        assert len(categories) > 0
    
    def test_regular_categories_contains_expected(self, client):
        """Test that expected categories are present."""
        response = client.get("/api/regular-categories")
        
        assert response.status_code == 200
        categories = response.json()
        
        category_names = set(categories)
        expected = {"Aluguel", "Internet", "Cemig"}
        
        for cat in expected:
            assert cat in category_names


class TestVariableExpensesEndpoint:
    """Tests for variable expenses CRUD endpoints."""
    
    def test_create_variable_expense(self, client):
        """Test creating a new variable expense."""
        data = {
            "place": "Mercado",
            "day": 15,
            "month": 5,
            "year": 2026,
            "value": 100.50,
            "paid_by": "FAFA",
            "category_name": "Comida"
        }
        
        response = client.post("/api/variable-expense/", json=data)
        
        assert response.status_code == 200
        expense = response.json()
        
        assert expense["place"] == "Mercado"
        assert expense["value"] == 100.50
        assert expense["paid_by"] == "FAFA"
    
    def test_list_variable_expenses(self, client):
        """Test listing variable expenses."""
        # First create some expenses
        data = {
            "place": "Mercado",
            "day": 15,
            "month": 5,
            "year": 2026,
            "value": 100.50,
            "paid_by": "FAFA",
            "category_name": "Comida"
        }
        
        client.post("/api/variable-expense/", json=data)
        
        # Now list them
        response = client.get("/api/variable-expenses/")
        
        assert response.status_code == 200
        expenses = response.json()
        
        assert isinstance(expenses, list)
        assert len(expenses) >= 1
    
    def test_list_variable_expenses_with_filters(self, client):
        """Test filtering variable expenses."""
        # Create an expense for month 5
        data = {
            "place": "Mercado",
            "day": 15,
            "month": 5,
            "year": 2026,
            "value": 100.50,
            "paid_by": "FAFA",
            "category_name": "Comida"
        }
        
        client.post("/api/variable-expense/", json=data)
        
        # Filter by month
        response = client.get("/api/variable-expenses/?month=5&year=2026")
        
        assert response.status_code == 200
        expenses = response.json()
        
        # Should have at least our created expense
        assert len(expenses) >= 1
    
    def test_delete_variable_expense(self, client):
        """Test deleting a variable expense."""
        # Create expense first
        data = {
            "place": "Mercado",
            "day": 15,
            "month": 5,
            "year": 2026,
            "value": 100.50,
            "paid_by": "FAFA",
            "category_name": "Comida"
        }
        
        create_response = client.post("/api/variable-expense/", json=data)
        expense_id = create_response.json()["id"]
        
        # Delete it
        delete_response = client.delete(f"/api/variable-expenses/{expense_id}")
        
        assert delete_response.status_code == 200
    
    def test_delete_nonexistent_variable_expense(self, client):
        """Test deleting a non-existent expense returns 404."""
        response = client.delete("/api/variable-expenses/9999")
        
        assert response.status_code == 404


class TestRegularExpensesEndpoint:
    """Tests for regular expenses CRUD endpoints."""
    
    def test_create_regular_expense(self, client):
        """Test creating a new regular expense (upsert)."""
        data = {
            "day": 5,
            "month": 5,
            "year": 2026,
            "value": 1500.00,
            "paid_by": "FAFA",
            "category_name": "Aluguel"
        }
        
        response = client.post("/api/regular-expense/", json=data)
        
        assert response.status_code == 200
        expense = response.json()
        
        assert expense["day"] == 5
        assert expense["value"] == 1500.00
    
    def test_update_regular_expense(self, client):
        """Test updating a regular expense (upsert)."""
        # Create first expense
        data1 = {
            "day": 5,
            "month": 5,
            "year": 2026,
            "value": 1500.00,
            "paid_by": "FAFA",
            "category_name": "Aluguel"
        }
        
        client.post("/api/regular-expense/", json=data1)
        
        # Update with same category+month
        data2 = {
            "day": 10,
            "month": 5,
            "year": 2026,
            "value": 2000.00,
            "paid_by": "FAFA",
            "category_name": "Aluguel"
        }
        
        update_response = client.post("/api/regular-expense/", json=data2)
        expense = update_response.json()
        
        assert expense["value"] == 2000.00
    
    def test_list_regular_expenses(self, client):
        """Test listing regular expenses."""
        # Create an expense first
        data = {
            "day": 5,
            "month": 5,
            "year": 2026,
            "value": 1500.00,
            "paid_by": "FAFA",
            "category_name": "Aluguel"
        }
        
        client.post("/api/regular-expense/", json=data)
        
        # List them
        response = client.get("/api/regular-expense/")
        
        assert response.status_code == 200
        expenses = response.json()
        
        assert isinstance(expenses, list)


class TestMonthRatioEndpoint:
    """Tests for month ratio endpoints."""
    
    def test_get_month_ratio(self, client):
        """Test getting month ratio."""
        response = client.get("/api/month-ratio?month=5&year=2026")
        
        assert response.status_code == 200
        ratio = response.json()
        
        assert "fafa_ratio" in ratio
        assert "fefe_ratio" in ratio
    
    def test_set_month_ratio(self, client):
        """Test setting a custom month ratio."""
        data = {
            "month": 5,
            "year": 2026,
            "fafa_ratio": 0.75
        }
        
        response = client.put("/api/month-ratio", json=data)
        
        assert response.status_code == 200
        ratio = response.json()
        
        assert ratio["fafa_ratio"] == 0.75
    
    def test_month_ratios_sum_to_one(self, client):
        """Test that fafa_ratio and fefe_ratio always sum to 1."""
        data = {
            "month": 5,
            "year": 2026,
            "fafa_ratio": 0.6667
        }
        
        client.put("/api/month-ratio", json=data)
        
        response = client.get("/api/month-ratio?month=5&year=2026")
        ratio = response.json()
        
        total = ratio["fafa_ratio"] + ratio["fefe_ratio"]
        assert abs(total - 1.0) < 0.0001


class TestBalanceEndpoint:
    """Tests for balance endpoint."""
    
    def test_get_balance(self, client):
        """Test getting monthly balance."""
        response = client.get("/api/balance?month=5&year=2026")
        
        assert response.status_code == 200
        balance = response.json()
        
        # Check all required fields
        required_fields = [
            "month", "year", "total_expenses", "variable_total",
            "regular_total", "fafa_ratio", "fefe_ratio",
            "fafa_should_pay", "fefe_should_pay", "fafa_paid",
            "fefe_paid", "balance"
        ]
        
        for field in required_fields:
            assert field in balance
    
    def test_balance_values_are_numbers(self, client):
        """Test that all numeric values are proper numbers."""
        response = client.get("/api/balance?month=5&year=2026")
        
        assert response.status_code == 200
        balance = response.json()
        
        for key in ["total_expenses", "variable_total", "regular_total",
                    "fafa_ratio", "fefe_ratio", "fafa_should_pay",
                    "fefe_should_pay", "fafa_paid", "fefe_paid", "balance"]:
            assert isinstance(balance[key], (int, float))


class TestAPIValidation:
    """Tests for API input validation."""
    
    def test_variable_expense_invalid_paid_by(self, client):
        """Test that invalid paid_by is rejected."""
        data = {
            "place": "Mercado",
            "day": 15,
            "month": 5,
            "year": 2026,
            "value": 100.50,
            "paid_by": "INVALID",  # Should be FAFA or FEFE
            "category_name": "Comida"
        }
        
        response = client.post("/api/variable-expense/", json=data)
        
        assert response.status_code == 422  # Validation error
    
    def test_variable_expense_negative_value(self, client):
        """Test that negative value is rejected."""
        data = {
            "place": "Mercado",
            "day": 15,
            "month": 5,
            "year": 2026,
            "value": -100.50,
            "paid_by": "FAFA",
            "category_name": "Comida"
        }
        
        response = client.post("/api/variable-expense/", json=data)
        
        assert response.status_code == 422
    
    def test_variable_expense_zero_value(self, client):
        """Test that zero value is rejected."""
        data = {
            "place": "Mercado",
            "day": 15,
            "month": 5,
            "year": 2026,
            "value": 0,
            "paid_by": "FAFA",
            "category_name": "Comida"
        }
        
        response = client.post("/api/variable-expense/", json=data)
        
        assert response.status_code == 422
    
    def test_month_ratio_invalid_ratio(self, client):
        """Test that invalid ratio is rejected."""
        data = {
            "month": 5,
            "year": 2026,
            "fafa_ratio": 1.5  # Must be between 0 and 1
        }
        
        response = client.put("/api/month-ratio", json=data)
        
        assert response.status_code == 422
