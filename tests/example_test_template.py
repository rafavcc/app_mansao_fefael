"""
Template para criar novos testes.

Copie este arquivo como `test_novo_feature.py` e adapte conforme necessário.
"""


class TestNovaFeature:
    """Testes para nova feature."""
    
    def test_cenario_basico(self, db_session):
        """Teste do cenário básico da nova feature."""
        
        # Arrange: Preparar dados de teste
        user = crud.create_user(db_session, name="TEST", full_name="Test")
        
        # Act: Executar a ação
        result = some_function(db_session, ...)
        
        # Assert: Verificar o resultado
        assert result == expected_value
    
    def test_cenario_com_erro(self, db_session):
        """Teste de erro da nova feature."""
        
        # Arrange
        data_invalida = {...}
        
        # Act + Assert: Esperar exceção
        with pytest.raises(Exception) as exc_info:
            some_function(db_session, data_invalida)
        
        assert "mensagem esperada" in str(exc_info.value)


class TestNovaFeatureAPI:
    """Testes para endpoints da nova feature."""
    
    def test_create_endpoint(self, client):
        """Teste de criar recurso via API."""
        
        # Arrange
        data = {...}
        
        # Act
        response = client.post("/api/nova-feature", json=data)
        
        # Assert
        assert response.status_code == 200
        result = response.json()
        assert result["field"] == expected_value
    
    def test_list_endpoint(self, client):
        """Teste de listar recursos via API."""
        
        # Arrange: Criar alguns dados primeiro
        crud.create_something(db_session, ...)
        
        # Act
        response = client.get("/api/nova-feature")
        
        # Assert
        assert response.status_code == 200
        items = response.json()
        assert len(items) >= 1
    
    def test_validation_error(self, client):
        """Teste de validação de input inválido."""
        
        # Arrange
        data_invalida = {...}
        
        # Act + Assert
        response = client.post("/api/nova-feature", json=data_invalida)
        assert response.status_code == 422
