"""
Тестовый скрипт для проверки MinIO endpoint.
Использование: python test_minio_endpoint.py
"""

import requests
import json
import sys

# Конфигурация
API_URL = "http://localhost:8010"
TEST_FILE_PATH = "documents/test/smeta_example.pdf"  # Путь к файлу в MinIO


def test_health_check():
    """Проверка health endpoint."""
    print("🔍 Проверка health endpoint...")
    try:
        response = requests.get(f"{API_URL}/health")
        response.raise_for_status()
        
        data = response.json()
        print(f"✅ Статус: {data['status']}")
        print(f"   Crew initialized: {data['crew_initialized']}")
        print(f"   MinIO configured: {data['minio_configured']}")
        
        if not data['minio_configured']:
            print("⚠️  Внимание: MinIO не настроен!")
            return False
        
        return True
    except Exception as e:
        print(f"❌ Ошибка health check: {str(e)}")
        return False


def test_minio_endpoint(file_path: str, bucket_name: str = None):
    """Тест обработки PDF из MinIO."""
    print(f"\n📄 Тест обработки PDF из MinIO...")
    print(f"   Путь: {file_path}")
    if bucket_name:
        print(f"   Bucket: {bucket_name}")
    
    payload = {"file_path": file_path}
    if bucket_name:
        payload["bucket_name"] = bucket_name
    
    try:
        response = requests.post(
            f"{API_URL}/predict_pdf_minio",
            json=payload,
            timeout=300  # 5 минут таймаут
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Успешно обработано!")
            print(f"   Источник: {data['source']}")
            print(f"   Файл: {data['filename']}")
            print(f"   Bucket: {data['bucket_name']}")
            print(f"   Обработано таблиц: {data['tables_processed']}")
            
            # Показать результаты каждой таблицы
            for result in data['results']:
                table_idx = result['table_index']
                status = result['status']
                
                if status == 'success':
                    output = result['output']
                    verdict = output.get('audit_verdict', {})
                    is_approved = verdict.get('is_approved', False)
                    total = verdict.get('calculated_total', 0)
                    
                    print(f"\n   Таблица {table_idx}:")
                    print(f"     Статус: {'✅ ОДОБРЕНО' if is_approved else '❌ НЕ ОДОБРЕНО'}")
                    print(f"     Сумма: {total:.2f}")
                else:
                    error = result.get('error', 'Unknown error')
                    print(f"\n   Таблица {table_idx}:")
                    print(f"     Статус: ❌ ОШИБКА")
                    print(f"     Причина: {error}")
            
            return True
        
        elif response.status_code == 404:
            print(f"❌ Файл не найден в MinIO: {file_path}")
            return False
        
        elif response.status_code == 403:
            print(f"❌ Доступ запрещен к файлу: {file_path}")
            print("   Проверьте MinIO credentials")
            return False
        
        elif response.status_code == 503:
            print(f"❌ Сервис недоступен")
            error_detail = response.json().get('detail', 'Unknown error')
            print(f"   Причина: {error_detail}")
            return False
        
        else:
            print(f"❌ Ошибка {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Детали: {error_data.get('detail', 'No details')}")
            except:
                print(f"   Ответ: {response.text[:200]}")
            return False
    
    except requests.exceptions.Timeout:
        print(f"❌ Таймаут запроса (>5 минут)")
        return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Не удалось подключиться к {API_URL}")
        print("   Убедитесь что сервис запущен")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {str(e)}")
        return False


def test_invalid_file_type():
    """Тест с неправильным типом файла."""
    print(f"\n🧪 Тест с неправильным типом файла...")
    
    try:
        response = requests.post(
            f"{API_URL}/predict_pdf_minio",
            json={"file_path": "documents/test/file.txt"}
        )
        
        if response.status_code == 400:
            print("✅ Правильно отклонен не-PDF файл")
            return True
        else:
            print(f"❌ Неожиданный статус: {response.status_code}")
            return False
    
    except Exception as e:
        print(f"❌ Ошибка теста: {str(e)}")
        return False


def main():
    """Основная функция тестирования."""
    print("=" * 60)
    print("🧪 Тестирование MinIO Integration")
    print("=" * 60)
    
    # 1. Health check
    if not test_health_check():
        print("\n⚠️  Health check failed. Продолжаем с осторожностью...")
    
    # 2. Тест основного endpoint
    success = test_minio_endpoint(TEST_FILE_PATH)
    
    # 3. Тест с неправильным типом файла
    test_invalid_file_type()
    
    # Итог
    print("\n" + "=" * 60)
    if success:
        print("✅ Все тесты прошли успешно!")
        print("=" * 60)
        return 0
    else:
        print("❌ Некоторые тесты не прошли")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    # Можно передать свой путь к файлу как аргумент
    if len(sys.argv) > 1:
        TEST_FILE_PATH = sys.argv[1]
    
    exit_code = main()
    sys.exit(exit_code)


