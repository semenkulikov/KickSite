#!/bin/bash

echo "🚀 Deploying performance optimizations..."

# 1. Остановка сервера если запущен
echo "📋 Stopping server if running..."
pkill -f "python manage.py runserver" || true
sleep 2

# 2. Обновление зависимостей
echo "📦 Updating dependencies..."
pip install -r requirements.txt

# 3. Сборка фронтенда
echo "🔨 Building frontend..."
npm run build

# 4. Применение миграций
echo "🗄️ Applying migrations..."
python manage.py migrate

# 5. Запуск сервера в фоне
echo "🌐 Starting server..."
python manage.py runserver 0.0.0.0:8000 &
SERVER_PID=$!
sleep 5

# 6. Тестирование производительности
echo "🧪 Testing performance..."
python test_process_performance.py

# 7. Проверка статуса сервера
if kill -0 $SERVER_PID 2>/dev/null; then
    echo "✅ Server is running (PID: $SERVER_PID)"
    echo "🌍 Access the application at: http://localhost:8000"
else
    echo "❌ Server failed to start"
    exit 1
fi

echo "🎉 Deployment completed successfully!"
echo ""
echo "📊 Performance optimizations applied:"
echo "   - Process-based message sending"
echo "   - Aggressive process termination"
echo "   - Optimized batch processing"
echo "   - Enhanced error handling"
echo ""
echo "🔧 To stop the server: kill $SERVER_PID" 