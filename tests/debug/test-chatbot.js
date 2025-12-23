// Test script to verify chatbot functionality
// Run with: node test-chatbot.js

const testChatbot = async () => {
  try {
    console.log('Testing chatbot API...');
    
    const response = await fetch('http://localhost:3000/api/chatbot/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: 'What are the recent sentiment trends?',
        userId: 'test-user-id',
        conversationHistory: [],
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    console.log('✅ Chatbot API Response:');
    console.log('Response:', data.response);
    console.log('RAG Context:', data.ragContext);
    console.log('Timestamp:', data.timestamp);
    
  } catch (error) {
    console.error('❌ Chatbot test failed:', error.message);
    console.log('Make sure:');
    console.log('1. The development server is running (npm run dev)');
    console.log('2. OPENAI_API_KEY is set in .env.local');
    console.log('3. Database is accessible');
  }
};

// Only run if this file is executed directly
if (require.main === module) {
  testChatbot();
}

module.exports = { testChatbot };
