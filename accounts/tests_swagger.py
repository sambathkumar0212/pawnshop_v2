from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status


class SwaggerAndDocsAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_openapi_schema_endpoint(self):
        response = self.client.get('/api/schema/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_swagger_ui_endpoint(self):
        response = self.client.get('/api/docs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_redoc_ui_endpoint(self):
        response = self.client.get('/api/redoc/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
