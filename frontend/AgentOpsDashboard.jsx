import React, { useState, useEffect, useRef } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line } from 'recharts';
import { Activity, CheckCircle, AlertTriangle, Clock, Zap, Users, MessageSquare, TrendingUp, Send, Plus, RefreshCw, X, Bot, User } from 'lucide-react';

const COLORS = ['#10B981', '#3B82F6', '#F59E0B', '#EF4444', '#8B5CF6'];
const API_BASE = 'http://localhost:8000';

const AgentOpsDashboard = () => {
  // Tab state
  const [activeTab, setActiveTab] = useState('dashboard');
  
  // Dashboard metrics
  const [metrics, setMetrics] = useState({
    totalTickets: 0,
    autoResolved: 0,
    automationRate: 0,
    avgResolutionTime: 0,
    escalationRate: 0,
    activeWorkflows: 0
  });

  const [selectedTimeRange, setSelectedTimeRange] = useState('24h');

  // Chat state
  const [chatMessages, setChatMessages] = useState([
    { role: 'assistant', content: "Hello! I'm your IT Support Assistant. How can I help you today? I can assist with VPN issues, password resets, software problems, and more." }
  ]);
  const [chatInput, setChatInput] = useState('');
  const [conversationId, setConversationId] = useState(null);
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [suggestedActions, setSuggestedActions] = useState(['Create a ticket', 'Check VPN status', 'Reset password']);
  const chatEndRef = useRef(null);

  // Tickets state
  const [tickets, setTickets] = useState([]);
  const [isLoadingTickets, setIsLoadingTickets] = useState(false);
  const [showNewTicketForm, setShowNewTicketForm] = useState(false);
  const [newTicket, setNewTicket] = useState({ title: '', description: '', category: 'other', priority: 'medium' });

  // Scroll chat to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  // Fetch dashboard data
  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/v1/analytics/dashboard`);
      if (response.ok) {
        const data = await response.json();
        setMetrics({
          totalTickets: data.total_tickets,
          autoResolved: data.auto_resolved,
          automationRate: (data.auto_resolved / data.total_tickets * 100).toFixed(1),
          avgResolutionTime: data.avg_resolution_time_minutes,
          escalationRate: (data.escalated / data.total_tickets * 100).toFixed(1),
          activeWorkflows: 12
        });
      }
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
    }
  };

  // Chat functions
  const sendChatMessage = async (message) => {
    if (!message.trim()) return;

    // Add user message to chat
    setChatMessages(prev => [...prev, { role: 'user', content: message }]);
    setChatInput('');
    setIsChatLoading(true);

    try {
      const response = await fetch(`${API_BASE}/api/v1/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: message,
          conversation_id: conversationId  // THIS IS THE KEY - pass it back!
        })
      });

      if (response.ok) {
        const data = await response.json();
        
        // Store conversation ID for future messages
        setConversationId(data.conversation_id);
        
        // Add assistant response
        setChatMessages(prev => [...prev, { role: 'assistant', content: data.response }]);
        
        // Update suggested actions
        if (data.suggested_actions?.length > 0) {
          setSuggestedActions(data.suggested_actions);
        }

        // If a ticket was created, show notification and refresh tickets
        if (data.ticket_created) {
          // Could add a toast notification here
          console.log('Ticket created:', data.ticket_created);
          fetchTickets();
        }
      } else {
        setChatMessages(prev => [...prev, { 
          role: 'assistant', 
          content: "Sorry, I'm having trouble connecting to the server. Please try again." 
        }]);
      }
    } catch (error) {
      console.error('Chat error:', error);
      setChatMessages(prev => [...prev, { 
        role: 'assistant', 
        content: "Sorry, something went wrong. Please check if the backend server is running." 
      }]);
    } finally {
      setIsChatLoading(false);
    }
  };

  const handleChatKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendChatMessage(chatInput);
    }
  };

  const startNewChat = () => {
    setChatMessages([
      { role: 'assistant', content: "Hello! I'm your IT Support Assistant. How can I help you today?" }
    ]);
    setConversationId(null);
    setSuggestedActions(['Create a ticket', 'Check VPN status', 'Reset password']);
  };

  // Ticket functions
  const fetchTickets = async () => {
    setIsLoadingTickets(true);
    try {
      // In a real app, you'd have a /tickets endpoint that lists all tickets
      // For now, we'll just refresh the dashboard
      await fetchDashboardData();
    } catch (error) {
      console.error('Failed to fetch tickets:', error);
    } finally {
      setIsLoadingTickets(false);
    }
  };

  const createTicket = async () => {
    if (!newTicket.title.trim() || !newTicket.description.trim()) {
      alert('Please fill in title and description');
      return;
    }

    try {
      const response = await fetch(`${API_BASE}/api/v1/tickets`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: newTicket.title,
          description: newTicket.description,
          category: newTicket.category,
          priority: newTicket.priority
        })
      });

      if (response.ok) {
        const data = await response.json();
        setTickets(prev => [data, ...prev]);
        setShowNewTicketForm(false);
        setNewTicket({ title: '', description: '', category: 'other', priority: 'medium' });
        alert(`Ticket ${data.ticket_id} created successfully!`);
      }
    } catch (error) {
      console.error('Failed to create ticket:', error);
      alert('Failed to create ticket. Is the backend running?');
    }
  };

  // Static data for charts
  const categoryData = [
    { name: 'Access', count: 78, color: '#10B981' },
    { name: 'Network', count: 52, color: '#3B82F6' },
    { name: 'Software', count: 45, color: '#F59E0B' },
    { name: 'Email', count: 38, color: '#8B5CF6' },
    { name: 'Hardware', count: 34, color: '#EF4444' }
  ];

  const trendData = [
    { time: '00:00', tickets: 8, resolved: 6 },
    { time: '04:00', tickets: 5, resolved: 4 },
    { time: '08:00', tickets: 22, resolved: 18 },
    { time: '12:00', tickets: 35, resolved: 28 },
    { time: '16:00', tickets: 28, resolved: 24 },
    { time: '20:00', tickets: 15, resolved: 12 }
  ];

  const agentPerformance = [
    { name: 'Triage Agent', processed: 247, accuracy: 94.2 },
    { name: 'Resolution Agent', processed: 198, accuracy: 89.4 },
    { name: 'Compliance Agent', processed: 198, validations: 100 }
  ];

  const recentTickets = [
    { id: 'INC00847', title: 'VPN Connection Timeout', status: 'resolved', agent: 'Resolution Agent', time: '2m ago' },
    { id: 'INC00846', title: 'Password Reset Request', status: 'resolved', agent: 'Resolution Agent', time: '5m ago' },
    { id: 'INC00845', title: 'Outlook Sync Issue', status: 'in_progress', agent: 'Resolution Agent', time: '8m ago' },
    { id: 'INC00844', title: 'Software Installation', status: 'escalated', agent: 'Escalation Agent', time: '12m ago' },
    { id: 'INC00843', title: 'Account Lockout', status: 'resolved', agent: 'Resolution Agent', time: '15m ago' }
  ];

  const getStatusColor = (status) => {
    switch (status) {
      case 'resolved': return 'bg-emerald-100 text-emerald-800';
      case 'in_progress': return 'bg-blue-100 text-blue-800';
      case 'processing': return 'bg-blue-100 text-blue-800';
      case 'escalated': return 'bg-amber-100 text-amber-800';
      case 'new': return 'bg-gray-100 text-gray-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const MetricCard = ({ icon: Icon, title, value, subtext, trend, color = 'blue' }) => (
    <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-gray-500">{title}</p>
          <p className="mt-2 text-3xl font-bold text-gray-900">{value}</p>
          {subtext && <p className="mt-1 text-sm text-gray-500">{subtext}</p>}
        </div>
        <div className={`p-3 rounded-xl bg-${color}-50`}>
          <Icon className={`w-6 h-6 text-${color}-600`} />
        </div>
      </div>
      {trend && (
        <div className="mt-4 flex items-center">
          <TrendingUp className="w-4 h-4 text-emerald-500 mr-1" />
          <span className="text-sm text-emerald-600 font-medium">{trend}</span>
        </div>
      )}
    </div>
  );

  // Render Dashboard Tab
  const renderDashboard = () => (
    <>
      {/* Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <MetricCard
          icon={Activity}
          title="Total Tickets"
          value={metrics.totalTickets}
          subtext="Today"
          trend="+12% from yesterday"
          color="blue"
        />
        <MetricCard
          icon={CheckCircle}
          title="Auto-Resolved"
          value={metrics.autoResolved}
          subtext={`${metrics.automationRate}% automation rate`}
          trend="+5% improvement"
          color="emerald"
        />
        <MetricCard
          icon={Clock}
          title="Avg Resolution Time"
          value={`${metrics.avgResolutionTime}m`}
          subtext="Per ticket"
          trend="-2.3m faster"
          color="amber"
        />
        <MetricCard
          icon={AlertTriangle}
          title="Escalation Rate"
          value={`${metrics.escalationRate}%`}
          subtext={`${Math.round(metrics.totalTickets * metrics.escalationRate / 100)} escalated`}
          color="red"
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        <div className="lg:col-span-2 bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Ticket Resolution Trend</h3>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={trendData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
              <XAxis dataKey="time" stroke="#9CA3AF" fontSize={12} />
              <YAxis stroke="#9CA3AF" fontSize={12} />
              <Tooltip contentStyle={{ backgroundColor: '#fff', border: '1px solid #E5E7EB', borderRadius: '8px' }} />
              <Line type="monotone" dataKey="tickets" stroke="#3B82F6" strokeWidth={2} dot={{ fill: '#3B82F6' }} name="Received" />
              <Line type="monotone" dataKey="resolved" stroke="#10B981" strokeWidth={2} dot={{ fill: '#10B981' }} name="Resolved" />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">By Category</h3>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={categoryData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={2} dataKey="count">
                {categoryData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
          <div className="mt-4 space-y-2">
            {categoryData.map((item, index) => (
              <div key={index} className="flex items-center justify-between text-sm">
                <div className="flex items-center">
                  <div className="w-3 h-3 rounded-full mr-2" style={{ backgroundColor: item.color }}></div>
                  <span className="text-gray-600">{item.name}</span>
                </div>
                <span className="font-medium text-gray-900">{item.count}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Bottom Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Agent Performance</h3>
          <div className="space-y-4">
            {agentPerformance.map((agent, index) => (
              <div key={index} className="p-4 bg-gray-50 rounded-xl">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium text-gray-900">{agent.name}</span>
                  <span className="text-sm text-gray-500">{agent.processed} processed</span>
                </div>
                <div className="flex items-center">
                  <div className="flex-1 bg-gray-200 rounded-full h-2 mr-3">
                    <div className="bg-gradient-to-r from-blue-500 to-indigo-500 h-2 rounded-full" style={{ width: `${agent.accuracy || agent.validations}%` }}></div>
                  </div>
                  <span className="text-sm font-medium text-gray-700">{agent.accuracy ? `${agent.accuracy}%` : '100%'}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">Recent Activity</h3>
            <button className="text-sm text-blue-600 hover:text-blue-700 font-medium" onClick={() => setActiveTab('tickets')}>View All</button>
          </div>
          <div className="space-y-3">
            {recentTickets.map((ticket, index) => (
              <div key={index} className="flex items-center justify-between p-3 hover:bg-gray-50 rounded-xl transition-colors">
                <div className="flex items-center space-x-3">
                  <div className="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center">
                    <MessageSquare className="w-5 h-5 text-gray-500" />
                  </div>
                  <div>
                    <p className="font-medium text-gray-900 text-sm">{ticket.title}</p>
                    <p className="text-xs text-gray-500">{ticket.id} • {ticket.agent}</p>
                  </div>
                </div>
                <div className="flex items-center space-x-3">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(ticket.status)}`}>
                    {ticket.status.replace('_', ' ')}
                  </span>
                  <span className="text-xs text-gray-400">{ticket.time}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );

  // Render Chat Tab
  const renderChat = () => (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 h-[calc(100vh-200px)] flex flex-col">
      {/* Chat Header */}
      <div className="p-4 border-b border-gray-100 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-500 rounded-xl flex items-center justify-center">
            <Bot className="w-6 h-6 text-white" />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">IT Support Assistant</h3>
            <p className="text-xs text-gray-500">Powered by Claude AI</p>
          </div>
        </div>
        <button
          onClick={startNewChat}
          className="px-3 py-2 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors flex items-center space-x-1"
        >
          <RefreshCw className="w-4 h-4" />
          <span>New Chat</span>
        </button>
      </div>

      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {chatMessages.map((msg, index) => (
          <div key={index} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`flex items-start space-x-2 max-w-[80%] ${msg.role === 'user' ? 'flex-row-reverse space-x-reverse' : ''}`}>
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                msg.role === 'user' ? 'bg-blue-500' : 'bg-gray-100'
              }`}>
                {msg.role === 'user' ? (
                  <User className="w-5 h-5 text-white" />
                ) : (
                  <Bot className="w-5 h-5 text-gray-600" />
                )}
              </div>
              <div className={`p-3 rounded-2xl ${
                msg.role === 'user' 
                  ? 'bg-blue-500 text-white' 
                  : 'bg-gray-100 text-gray-900'
              }`}>
                <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
              </div>
            </div>
          </div>
        ))}
        {isChatLoading && (
          <div className="flex justify-start">
            <div className="flex items-start space-x-2">
              <div className="w-8 h-8 rounded-lg bg-gray-100 flex items-center justify-center">
                <Bot className="w-5 h-5 text-gray-600" />
              </div>
              <div className="p-3 rounded-2xl bg-gray-100">
                <div className="flex space-x-1">
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                </div>
              </div>
            </div>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      {/* Suggested Actions */}
      {suggestedActions.length > 0 && (
        <div className="px-4 py-2 border-t border-gray-100">
          <div className="flex flex-wrap gap-2">
            {suggestedActions.map((action, index) => (
              <button
                key={index}
                onClick={() => sendChatMessage(action)}
                className="px-3 py-1.5 text-xs font-medium text-blue-600 bg-blue-50 hover:bg-blue-100 rounded-full transition-colors"
              >
                {action}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Chat Input */}
      <div className="p-4 border-t border-gray-100">
        <div className="flex items-center space-x-2">
          <input
            type="text"
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            onKeyPress={handleChatKeyPress}
            placeholder="Type your message..."
            className="flex-1 px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            disabled={isChatLoading}
          />
          <button
            onClick={() => sendChatMessage(chatInput)}
            disabled={isChatLoading || !chatInput.trim()}
            className="p-3 bg-blue-500 hover:bg-blue-600 disabled:bg-gray-300 text-white rounded-xl transition-colors"
          >
            <Send className="w-5 h-5" />
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
        <div className="flex items-center space-x-3">
          <button
            onClick={fetchTickets}
            className="px-4 py-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors flex items-center space-x-2"
          >
            <RefreshCw className={`w-4 h-4 ${isLoadingTickets ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
          <button
            onClick={() => setShowNewTicketForm(true)}
            className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg transition-colors flex items-center space-x-2"
          >
            <Plus className="w-4 h-4" />
            <span>New Ticket</span>
          </button>
        </div>
      </div>

      {/* New Ticket Modal */}
      {showNewTicketForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl p-6 w-full max-w-md shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900">Create New Ticket</h3>
              <button onClick={() => setShowNewTicketForm(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
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
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 h-24"
                  placeholder="Detailed description of the problem..."
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
              <div className="flex justify-end space-x-3 pt-4">
                <button
                  onClick={() => setShowNewTicketForm(false)}
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

      {/* Tickets List */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100">
        <div className="p-4 border-b border-gray-100">
          <div className="flex items-center space-x-4">
            <input
              type="text"
              placeholder="Search tickets..."
              className="flex-1 px-4 py-2 bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
        <div className="divide-y divide-gray-100">
          {[...tickets, ...recentTickets].map((ticket, index) => (
            <div key={index} className="p-4 hover:bg-gray-50 transition-colors">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-4">
                  <div className="w-12 h-12 bg-gray-100 rounded-xl flex items-center justify-center">
                    <MessageSquare className="w-6 h-6 text-gray-500" />
                  </div>
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="font-mono text-sm text-blue-600">{ticket.ticket_id || ticket.id}</span>
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${getStatusColor(ticket.status)}`}>
                        {ticket.status?.replace('_', ' ')}
                      </span>
                    </div>
                    <p className="font-medium text-gray-900 mt-1">{ticket.title}</p>
                    <p className="text-sm text-gray-500 mt-0.5">
                      {ticket.category && <span className="capitalize">{ticket.category} • </span>}
                      {ticket.agent || ticket.created_at || ticket.time}
                    </p>
                  </div>
                </div>
                <button className="px-3 py-1.5 text-sm text-blue-600 hover:bg-blue-50 rounded-lg transition-colors">
                  View Details
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-xl flex items-center justify-center">
                <Zap className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-gray-900">AgentOps AI</h1>
                <p className="text-sm text-gray-500">Intelligent IT Operations</p>
              </div>
            </div>
            
            {/* Navigation Tabs */}
            <div className="flex items-center space-x-1 bg-gray-100 rounded-lg p-1">
              {['dashboard', 'chat', 'tickets'].map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors capitalize ${
                    activeTab === tab
                      ? 'bg-white text-gray-900 shadow-sm'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  {tab}
                </button>
              ))}
            </div>

            <div className="flex items-center space-x-4">
              <select
                value={selectedTimeRange}
                onChange={(e) => setSelectedTimeRange(e.target.value)}
                className="px-4 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm font-medium text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="1h">Last Hour</option>
                <option value="24h">Last 24 Hours</option>
                <option value="7d">Last 7 Days</option>
                <option value="30d">Last 30 Days</option>
              </select>
              <div className="flex items-center space-x-2 px-3 py-2 bg-emerald-50 rounded-lg">
                <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse"></div>
                <span className="text-sm font-medium text-emerald-700">System Healthy</span>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        {activeTab === 'dashboard' && renderDashboard()}
        {activeTab === 'chat' && renderChat()}
        {activeTab === 'tickets' && renderTickets()}
      </main>
    </div>
  );
};

export default AgentOpsDashboard;