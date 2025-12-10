#!/usr/bin/env python3
"""
Тест endpoint /predict_pdf с внешнего клиента
Используйте этот скрипт для проверки доступа к серверу на RunPod
"""
import requests
import sys
from pathlib import Path

# ЗАМЕНИТЕ НА ВАШ ПУБЛИЧНЫЙ URL ОТ RUNPOD!
# Например: "https://xxxxxxxx-8000.proxy.runpod.net"
SERVER_URL = "http://YOUR_RUNPOD_PUBLIC_URL/predict_pdf"

def test_pdf_upload(pdf_path: str):
    """Тестирует загрузку PDF на удаленный сервер"""
    
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        print(f"❌ Файл не найден: {pdf_path}")
        return False
    
    print("="*80)
    print("🧪 ТЕСТ: Удаленная загрузка PDF на RunPod")
    print("="*80)
    print(f"\nСервер: {SERVER_URL}")
    print(f"Файл: {pdf_file.name}")
    print(f"Размер: {pdf_file.stat().st_size / 1024:.1f} KB")
    print(f"\n📤 Отправка...")
    
    try:
        # Открываем и отправляем PDF
        with open(pdf_file, 'rb') as f:
            files = {'file': (pdf_file.name, f, 'application/pdf')}
            
            response = requests.post(
                SERVER_URL,
                files=files,
                timeout=300  # 5 минут на обработку
            )
        
        print(f"✓ Статус: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            print("\n" + "="*80)
            print("✅ РЕЗУЛЬТАТ:")
            print("="*80)
            
            print(f"\nФайл: {result.get('filename')}")
            print(f"Таблиц обработано: {result.get('tables_processed')}")
            
            results = result.get('results', [])
            success_count = sum(1 for r in results if r['status'] == 'success')
            
            print(f"\nРезультаты проверки:")
            print(f"  ✅ Успешно: {success_count}/{len(results)}")
            print(f"  ❌ Ошибок: {len(results) - success_count}")
            
            # Показываем детали первых 3 таблиц
            print(f"\nПервые таблицы:")
            for i, res in enumerate(results[:3], 1):
                print(f"\n  Таблица {res['table_index']}:")
                if res['status'] == 'success':
                    output = res['output']
                    raw_input = output.get('raw_input', {})
                    verdict = output.get('audit_verdict', {})
                    
                    print(f"    ✅ Успешно")
                    print(f"    Таблица СЦП: {raw_input.get('table_code_claimed')}")
                    print(f"    Позиция: {raw_input.get('position_number')}")
                    print(f"    Одобрено: {'✅ ДА' if verdict.get('is_approved') else '❌ НЕТ'}")
                else:
                    print(f"    ❌ Ошибка: {res.get('error', 'Unknown')[:100]}...")
            
            print("\n" + "="*80)
            print("✅ PDF УСПЕШНО ОБРАБОТАН!")
            print("="*80)
            return True
            
        else:
            print(f"\n❌ Ошибка HTTP {response.status_code}")
            try:
                print(f"Детали: {response.json()}")
            except:
                print(f"Ответ: {response.text[:500]}")
            return False
            
    except requests.exceptions.Timeout:
        print("\n❌ ТАЙМАУТ: Обработка заняла более 5 минут")
        return False
    except requests.exceptions.ConnectionError:
        print(f"\n❌ ОШИБКА ПОДКЛЮЧЕНИЯ: Не удается подключиться к серверу")
        print(f"Проверьте:")
        print(f"  1. Сервер запущен на RunPod")
        print(f"  2. Порт 8000 открыт в TCP Port Mappings")
        print(f"  3. SERVER_URL в скрипте правильный")
        return False
    except Exception as e:
        print(f"\n❌ Ошибка: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    if SERVER_URL == "http://YOUR_RUNPOD_PUBLIC_URL/predict_pdf":
        print("❌ ОШИБКА: Не установлен SERVER_URL!")
        print("\nОткройте RunPod Web UI:")
        print("  1. Найдите ваш Pod")
        print("  2. В разделе 'TCP Port Mappings' добавьте порт 8000")
        print("  3. Скопируйте публичный URL (например: https://xxxxxxxx-8000.proxy.runpod.net)")
        print("  4. Замените SERVER_URL в этом скрипте")
        print("\nПример:")
        print('  SERVER_URL = "https://abc123-8000.proxy.runpod.net/predict_pdf"')
        sys.exit(1)
    
    if len(sys.argv) < 2:
        print("Использование: python test_remote_pdf.py path/to/file.pdf")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    success = test_pdf_upload(pdf_path)
    sys.exit(0 if success else 1)

