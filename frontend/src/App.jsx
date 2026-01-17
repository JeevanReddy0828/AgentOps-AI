import React, { useState, useEffect, useRef } from 'react';

const API_BASE = 'http://localhost:8000';

// Icons as simple SVG components
const Icons = {
  Zap: () => (
    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
    </svg>
  ),
  Send: () => (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
    </svg>
  ),
  Bot: () => (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
    </svg>
  ),
  User: () => (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
    </svg>
  ),
  Refresh: () => (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
    </svg>
  ),
  Plus: () => (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
    </svg>
  ),
  X: () => (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  ),
  Ticket: () => (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 5v2m0 4v2m0 4v2M5 5a2 2 0 00-2 2v3a2 2 0 110 4v3a2 2 0 002 2h14a2 2 0 002-2v-3a2 2 0 110-4V7a2 2 0 00-2-2H5z" />
    </svg>
  ),
  Chart: () => (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
    </svg>
  ),
  Chat: () => (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
    </svg>
  ),
  Check: () => (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  ),
  Clock: () => (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  ),
  Alert: () => (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
    </svg>
  ),
};

function App() {
  const [activeTab, setActiveTab] = useState('chat');
  
  // Chat state
  const [messages, setMessages] = useState([
    { role: 'assistant', content: "Hello! I'm your IT Support Assistant. How can I help you today? I can assist with VPN issues, password resets, software problems, and more." }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [conversationId, setConversationId] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [suggestedActions, setSuggestedActions] = useState(['VPN not working', 'Reset my password', 'Software installation']);
  const messagesEndRef = useRef(null);

  // Tickets state
  const [tickets, setTickets] = useState([]);
  const [showNewTicketModal, setShowNewTicketModal] = useState(false);
  const [newTicket, setNewTicket] = useState({ title: '', description: '', category: 'other', priority: 'medium' });
  const [isLoadingTickets, setIsLoadingTickets] = useState(false);
  const [selectedTicket, setSelectedTicket] = useState(null);
  const [showTicketDetail, setShowTicketDetail] = useState(false);
  const [ticketStatus, setTicketStatus] = useState(null);

  // Dashboard state
  const [dashboardData, setDashboardData] = useState({
    total_tickets: 0,
    resolved_tickets: 0,
    auto_resolved: 0,
    escalated: 0,
    avg_resolution_time_minutes: 0,
    resolution_rate: 0,
    top_categories: {}
  });

  // Auto scroll chat
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Fetch dashboard data on mount
  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/v1/analytics/dashboard`);
      if (response.ok) {
        const data = await response.json();
        setDashboardData(data);
      }
    } catch (error) {
      console.error('Failed to fetch dashboard:', error);
    }
  };

  // Send chat message
  const sendMessage = async (messageText) => {
    const text = messageText || inputValue;
    if (!text.trim() || isLoading) return;

    // Add user message
    setMessages(prev => [...prev, { role: 'user', content: text }]);
    setInputValue('');
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE}/api/v1/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          conversation_id: conversationId  // KEY: Pass conversation_id back!
        })
      });

      if (response.ok) {
        const data = await response.json();
        
        // Store conversation_id for next message
        setConversationId(data.conversation_id);
        
        // Add assistant response
        setMessages(prev => [...prev, { role: 'assistant', content: data.response }]);
        
        // Update suggested actions
        if (data.suggested_actions?.length) {
          setSuggestedActions(data.suggested_actions);
        }

        // If ticket was created, refresh tickets list and show notification
        if (data.ticket_created) {
          console.log('Ticket created:', data.ticket_created);
          fetchTickets();
          // Add to local tickets list immediately
          setTickets(prev => [{
            ticket_id: data.ticket_created,
            title: 'Support Request from Chat',
            status: 'new',
            created_at: new Date().toISOString()
          }, ...prev]);
        }
      } else {
        throw new Error('API request failed');
      }
    } catch (error) {
      console.error('Chat error:', error);
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: "Sorry, I'm having trouble connecting. Please make sure the backend server is running on port 8000." 
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const startNewChat = () => {
    setMessages([
      { role: 'assistant', content: "Hello! I'm your IT Support Assistant. How can I help you today?" }
    ]);
    setConversationId(null);
    setSuggestedActions(['VPN not working', 'Reset my password', 'Software installation']);
  };

  // Fetch tickets
  const fetchTickets = async () => {
    setIsLoadingTickets(true);
    try {
      // Note: You'd need to add a GET /api/v1/tickets endpoint to list all tickets
      // For now we'll just use the local state
    } catch (error) {
      console.error('Failed to fetch tickets:', error);
    } finally {
      setIsLoadingTickets(false);
    }
  };

  // Fetch single ticket details
  const fetchTicketDetails = async (ticketId) => {
    try {
      const [ticketRes, statusRes] = await Promise.all([
        fetch(`${API_BASE}/api/v1/tickets/${ticketId}`),
        fetch(`${API_BASE}/api/v1/tickets/${ticketId}/status`)
      ]);

      if (ticketRes.ok) {
        const ticketData = await ticketRes.json();
        setSelectedTicket(ticketData);
      }

      if (statusRes.ok) {
        const statusData = await statusRes.json();
        setTicketStatus(statusData);
      }

      setShowTicketDetail(true);
    } catch (error) {
      console.error('Failed to fetch ticket details:', error);
      alert('Failed to load ticket details. Make sure the backend is running.');
    }
  };

  // Close ticket detail modal
  const closeTicketDetail = () => {
    setShowTicketDetail(false);
    setSelectedTicket(null);
    setTicketStatus(null);
  };

  // Create ticket manually
  const createTicket = async () => {
    if (!newTicket.title || !newTicket.description) {
      alert('Please fill in title and description');
      return;
    }

    try {
      const response = await fetch(`${API_BASE}/api/v1/tickets`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newTicket)
      });

      if (response.ok) {
        const data = await response.json();
        setTickets(prev => [data, ...prev]);
        setShowNewTicketModal(false);
        setNewTicket({ title: '', description: '', category: 'other', priority: 'medium' });
        alert(`Ticket ${data.ticket_id} created successfully!`);
      }
    } catch (error) {
      console.error('Failed to create ticket:', error);
      alert('Failed to create ticket');
    }
  };

  const getStatusBadge = (status) => {
    const styles = {
      new: 'bg-gray-100 text-gray-800',
      processing: 'bg-blue-100 text-blue-800',
      in_progress: 'bg-blue-100 text-blue-800',
      resolved: 'bg-green-100 text-green-800',
      escalated: 'bg-yellow-100 text-yellow-800',
      closed: 'bg-gray-100 text-gray-600'
    };
    return styles[status] || styles.new;
  };

  // Render Chat Tab
  const renderChat = () => (
    <div className="flex flex-col h-[calc(100vh-140px)] bg-white rounded-xl shadow-sm border border-gray-200">
      {/* Chat Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center text-white">
            <Icons.Bot />
          </div>
          <div>
            <h2 className="font-semibold text-gray-900">AI IT Assistant</h2>
            <p className="text-xs text-gray-500">Powered by Claude + RAG</p>
          </div>
        </div>
        <button
          onClick={startNewChat}
          className="flex items-center gap-2 px-3 py-2 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition"
        >
          <Icons.Refresh />
          New Chat
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`flex gap-2 max-w-[80%] ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                msg.role === 'user' ? 'bg-blue-500 text-white' : 'bg-gray-100 text-gray-600'
              }`}>
                {msg.role === 'user' ? <Icons.User /> : <Icons.Bot />}
              </div>
              <div className={`px-4 py-3 rounded-2xl ${
                msg.role === 'user' 
                  ? 'bg-blue-500 text-white' 
                  : 'bg-gray-100 text-gray-900'
              }`}>
                <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
              </div>
            </div>
          </div>
        ))}
        
        {isLoading && (
          <div className="flex justify-start">
            <div className="flex gap-2">
              <div className="w-8 h-8 rounded-lg bg-gray-100 flex items-center justify-center text-gray-600">
                <Icons.Bot />
              </div>
              <div className="px-4 py-3 rounded-2xl bg-gray-100">
                <div className="flex gap-1">
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                </div>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Suggested Actions */}
      <div className="px-4 py-2 border-t border-gray-100">
        <div className="flex flex-wrap gap-2">
          {suggestedActions.map((action, idx) => (
            <button
              key={idx}
              onClick={() => sendMessage(action)}
              className="px-3 py-1.5 text-xs font-medium text-blue-600 bg-blue-50 hover:bg-blue-100 rounded-full transition"
            >
              {action}
            </button>
          ))}
        </div>
      </div>

      {/* Input */}
      <div className="p-4 border-t border-gray-200">
        <div className="flex gap-2">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
            placeholder="Ask about IT issues, password resets, VPN help..."
            className="flex-1 px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            disabled={isLoading}
          />
          <button
            onClick={() => sendMessage()}
            disabled={isLoading || !inputValue.trim()}
            className="px-4 py-3 bg-blue-500 hover:bg-blue-600 disabled:bg-gray-300 text-white rounded-xl transition"
          >
            <Icons.Send />
          </button>
        </div>
      </div>
    </div>
  );

  // Render Tickets Tab
  const renderTickets = () => (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-gray-900">Support Tickets</h2>
        <button
          onClick={() => setShowNewTicketModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg transition"
        >
          <Icons.Plus />
          New Ticket
        </button>
      </div>

      {/* Tickets List */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200">
        {tickets.length === 0 ? (
          <div className="p-12 text-center">
            <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <Icons.Ticket />
            </div>
            <p className="text-gray-500">No tickets yet. Create one or use the AI Assistant!</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {tickets.map((ticket, idx) => (
              <div 
                key={idx} 
                className="p-4 hover:bg-gray-50 transition cursor-pointer"
                onClick={() => fetchTicketDetails(ticket.ticket_id)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center">
                      <Icons.Ticket />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-sm text-blue-600">{ticket.ticket_id}</span>
                        <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${getStatusBadge(ticket.status)}`}>
                          {ticket.status}
                        </span>
                      </div>
                      <p className="font-medium text-gray-900">{ticket.title}</p>
                      <p className="text-sm text-gray-500">
                        {ticket.category && `${ticket.category} • `}
                        {new Date(ticket.created_at).toLocaleString()}
                      </p>
                    </div>
                  </div>
                  <button 
                    className="px-3 py-1.5 text-sm text-blue-600 hover:bg-blue-50 rounded-lg transition"
                    onClick={(e) => {
                      e.stopPropagation();
                      fetchTicketDetails(ticket.ticket_id);
                    }}
                  >
                    View Details
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Ticket Detail Modal */}
      {showTicketDetail && selectedTicket && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-6 w-full max-w-2xl shadow-xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center text-blue-600">
                  <Icons.Ticket />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">{selectedTicket.ticket_id}</h3>
                  <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${getStatusBadge(selectedTicket.status)}`}>
                    {selectedTicket.status}
                  </span>
                </div>
              </div>
              <button onClick={closeTicketDetail} className="text-gray-400 hover:text-gray-600">
                <Icons.X />
              </button>
            </div>

            <div className="space-y-6">
              {/* Ticket Info */}
              <div>
                <h4 className="text-sm font-medium text-gray-500 mb-2">Title</h4>
                <p className="text-gray-900 font-medium">{selectedTicket.title}</p>
              </div>

              <div>
                <h4 className="text-sm font-medium text-gray-500 mb-2">Description</h4>
                <p className="text-gray-700 whitespace-pre-wrap bg-gray-50 p-4 rounded-lg">{selectedTicket.description}</p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <h4 className="text-sm font-medium text-gray-500 mb-2">Category</h4>
                  <p className="text-gray-900 capitalize">{selectedTicket.category || 'Not specified'}</p>
                </div>
                <div>
                  <h4 className="text-sm font-medium text-gray-500 mb-2">Priority</h4>
                  <p className="text-gray-900 capitalize">{selectedTicket.priority || 'Not specified'}</p>
                </div>
                <div>
                  <h4 className="text-sm font-medium text-gray-500 mb-2">Created At</h4>
                  <p className="text-gray-900">{new Date(selectedTicket.created_at).toLocaleString()}</p>
                </div>
                <div>
                  <h4 className="text-sm font-medium text-gray-500 mb-2">User Email</h4>
                  <p className="text-gray-900">{selectedTicket.user_email || 'Not provided'}</p>
                </div>
              </div>

              {/* Resolution Status */}
              {ticketStatus && (
                <div className="border-t border-gray-200 pt-6">
                  <h4 className="text-sm font-semibold text-gray-900 mb-4">Resolution Status</h4>
                  
                  <div className="space-y-4">
                    <div className="flex items-center gap-4">
                      <div className={`w-3 h-3 rounded-full ${ticketStatus.completed ? 'bg-green-500' : 'bg-yellow-500 animate-pulse'}`}></div>
                      <span className="text-gray-700">
                        {ticketStatus.completed ? 'Completed' : 'In Progress'}
                      </span>
                    </div>

                    {ticketStatus.escalated && (
                      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                        <div className="flex items-center gap-2 text-yellow-800 font-medium mb-1">
                          <Icons.Alert />
                          Escalated
                        </div>
                        <p className="text-yellow-700 text-sm">{ticketStatus.escalation_reason || 'Requires human intervention'}</p>
                      </div>
                    )}

                    {ticketStatus.resolution_summary && (
                      <div>
                        <h5 className="text-sm font-medium text-gray-500 mb-2">Resolution Summary</h5>
                        <p className="text-gray-700 bg-green-50 p-4 rounded-lg">{ticketStatus.resolution_summary}</p>
                      </div>
                    )}

                    {ticketStatus.actions_taken && ticketStatus.actions_taken.length > 0 && (
                      <div>
                        <h5 className="text-sm font-medium text-gray-500 mb-2">Actions Taken</h5>
                        <ul className="space-y-2">
                          {ticketStatus.actions_taken.map((action, idx) => (
                            <li key={idx} className="flex items-start gap-2 text-gray-700">
                              <Icons.Check />
                              <span>{action}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            <div className="flex justify-end gap-3 mt-6 pt-6 border-t border-gray-200">
              <button
                onClick={closeTicketDetail}
                className="px-4 py-2 text-gray-600 hover:text-gray-900"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* New Ticket Modal */}
      {showNewTicketModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-6 w-full max-w-md shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Create New Ticket</h3>
              <button onClick={() => setShowNewTicketModal(false)} className="text-gray-400 hover:text-gray-600">
                <Icons.X />
              </button>
            </div>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
                <input
                  type="text"
                  value={newTicket.title}
                  onChange={(e) => setNewTicket({ ...newTicket, title: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Brief description of the issue"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <textarea
                  value={newTicket.description}
                  onChange={(e) => setNewTicket({ ...newTicket, description: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 h-24 resize-none"
                  placeholder="Detailed description..."
                />
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
                  <select
                    value={newTicket.category}
                    onChange={(e) => setNewTicket({ ...newTicket, category: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="network">Network</option>
                    <option value="hardware">Hardware</option>
                    <option value="software">Software</option>
                    <option value="access">Access</option>
                    <option value="email">Email</option>
                    <option value="other">Other</option>
                  </select>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Priority</label>
                  <select
                    value={newTicket.priority}
                    onChange={(e) => setNewTicket({ ...newTicket, priority: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </select>
                </div>
              </div>
              
              <div className="flex justify-end gap-3 pt-4">
                <button
                  onClick={() => setShowNewTicketModal(false)}
                  className="px-4 py-2 text-gray-600 hover:text-gray-900"
                >
                  Cancel
                </button>
                <button
                  onClick={createTicket}
                  className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg"
                >
                  Create Ticket
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );

  // Render Dashboard Tab
  const renderDashboard = () => (
    <div className="space-y-6">
      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Total Tickets</p>
              <p className="text-3xl font-bold text-gray-900">{dashboardData.total_tickets}</p>
            </div>
            <div className="w-12 h-12 bg-blue-50 rounded-xl flex items-center justify-center text-blue-500">
              <Icons.Ticket />
            </div>
          </div>
        </div>
        
        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Auto-Resolved</p>
              <p className="text-3xl font-bold text-gray-900">{dashboardData.auto_resolved}</p>
              <p className="text-xs text-green-600">{((dashboardData.auto_resolved / dashboardData.total_tickets) * 100 || 0).toFixed(1)}% automation</p>
            </div>
            <div className="w-12 h-12 bg-green-50 rounded-xl flex items-center justify-center text-green-500">
              <Icons.Check />
            </div>
          </div>
        </div>
        
        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Avg Resolution Time</p>
              <p className="text-3xl font-bold text-gray-900">{dashboardData.avg_resolution_time_minutes}m</p>
            </div>
            <div className="w-12 h-12 bg-amber-50 rounded-xl flex items-center justify-center text-amber-500">
              <Icons.Clock />
            </div>
          </div>
        </div>
        
        <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Escalated</p>
              <p className="text-3xl font-bold text-gray-900">{dashboardData.escalated}</p>
              <p className="text-xs text-red-600">{((dashboardData.escalated / dashboardData.total_tickets) * 100 || 0).toFixed(1)}% rate</p>
            </div>
            <div className="w-12 h-12 bg-red-50 rounded-xl flex items-center justify-center text-red-500">
              <Icons.Alert />
            </div>
          </div>
        </div>
      </div>

      {/* Categories */}
      <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Tickets by Category</h3>
        <div className="space-y-3">
          {Object.entries(dashboardData.top_categories).map(([category, count]) => (
            <div key={category} className="flex items-center gap-4">
              <span className="w-24 text-sm text-gray-600 capitalize">{category}</span>
              <div className="flex-1 bg-gray-100 rounded-full h-4">
                <div 
                  className="bg-blue-500 h-4 rounded-full transition-all"
                  style={{ width: `${(count / Math.max(...Object.values(dashboardData.top_categories))) * 100}%` }}
                ></div>
              </div>
              <span className="w-12 text-sm font-medium text-gray-900 text-right">{count}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Agent Performance */}
      <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Agent Performance</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            { name: 'Triage Agent', processed: 150, accuracy: 94.2 },
            { name: 'Resolution Agent', processed: 120, accuracy: 89.4 },
            { name: 'Compliance Agent', processed: 120, accuracy: 100 }
          ].map((agent, idx) => (
            <div key={idx} className="p-4 bg-gray-50 rounded-xl">
              <p className="font-medium text-gray-900">{agent.name}</p>
              <p className="text-sm text-gray-500">{agent.processed} processed</p>
              <div className="mt-2 flex items-center gap-2">
                <div className="flex-1 bg-gray-200 rounded-full h-2">
                  <div className="bg-blue-500 h-2 rounded-full" style={{ width: `${agent.accuracy}%` }}></div>
                </div>
                <span className="text-sm font-medium">{agent.accuracy}%</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            {/* Logo */}
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-purple-600 rounded-xl flex items-center justify-center text-white">
                <Icons.Zap />
              </div>
              <div>
                <h1 className="text-xl font-bold text-gray-900">AgentOps AI</h1>
                <p className="text-xs text-gray-500">Intelligent IT Operations</p>
              </div>
            </div>

            {/* Navigation */}
            <nav className="flex items-center gap-1 bg-gray-100 rounded-lg p-1">
              {[
                { id: 'dashboard', label: 'Dashboard', icon: Icons.Chart },
                { id: 'tickets', label: 'Tickets', icon: Icons.Ticket },
                { id: 'chat', label: 'AI Assistant', icon: Icons.Chat }
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition ${
                    activeTab === tab.id
                      ? 'bg-white text-gray-900 shadow-sm'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  <tab.icon />
                  {tab.label}
                </button>
              ))}
            </nav>

            {/* Status */}
            <div className="flex items-center gap-2 px-3 py-2 bg-green-50 rounded-lg">
              <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
              <span className="text-sm font-medium text-green-700">System Healthy</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        {activeTab === 'dashboard' && renderDashboard()}
        {activeTab === 'tickets' && renderTickets()}
        {activeTab === 'chat' && renderChat()}
      </main>
    </div>
  );
}

export default App;