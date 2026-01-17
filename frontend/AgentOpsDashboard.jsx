import React, { useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line } from 'recharts';
import { Activity, CheckCircle, AlertTriangle, Clock, Zap, Users, MessageSquare, TrendingUp } from 'lucide-react';

const COLORS = ['#10B981', '#3B82F6', '#F59E0B', '#EF4444', '#8B5CF6'];

const AgentOpsDashboard = () => {
  const [metrics, setMetrics] = useState({
    totalTickets: 247,
    autoResolved: 176,
    automationRate: 71.3,
    avgResolutionTime: 8.5,
    escalationRate: 14.2,
    activeWorkflows: 12
  });

  const [selectedTimeRange, setSelectedTimeRange] = useState('24h');

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
      case 'escalated': return 'bg-amber-100 text-amber-800';
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
          {/* Ticket Trend */}
          <div className="lg:col-span-2 bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Ticket Resolution Trend</h3>
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                <XAxis dataKey="time" stroke="#9CA3AF" fontSize={12} />
                <YAxis stroke="#9CA3AF" fontSize={12} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#fff',
                    border: '1px solid #E5E7EB',
                    borderRadius: '8px'
                  }}
                />
                <Line type="monotone" dataKey="tickets" stroke="#3B82F6" strokeWidth={2} dot={{ fill: '#3B82F6' }} name="Received" />
                <Line type="monotone" dataKey="resolved" stroke="#10B981" strokeWidth={2} dot={{ fill: '#10B981' }} name="Resolved" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Category Distribution */}
          <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">By Category</h3>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={categoryData}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={80}
                  paddingAngle={2}
                  dataKey="count"
                >
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
          {/* Agent Performance */}
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
                      <div
                        className="bg-gradient-to-r from-blue-500 to-indigo-500 h-2 rounded-full"
                        style={{ width: `${agent.accuracy || agent.validations}%` }}
                      ></div>
                    </div>
                    <span className="text-sm font-medium text-gray-700">
                      {agent.accuracy ? `${agent.accuracy}%` : '100%'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Recent Tickets */}
          <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900">Recent Activity</h3>
              <button className="text-sm text-blue-600 hover:text-blue-700 font-medium">View All</button>
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
      </main>
    </div>
  );
};

export default AgentOpsDashboard;
