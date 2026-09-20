import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import DashboardLayout from './layouts/DashboardLayout'
import Dashboard from './pages/Dashboard'
import Traffic from './pages/Traffic'
import Pollution from './pages/Pollution'
import Energy from './pages/Energy'
import Weather from './pages/Weather'
import Planning from './pages/Planning'
import { PlannerProvider } from './context/PlannerContext'

export default function App() {
  return (
    <BrowserRouter>
      <PlannerProvider>
        <Routes>
          <Route element={<DashboardLayout />}>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/traffic" element={<Traffic />} />
            <Route path="/pollution" element={<Pollution />} />
            <Route path="/energy" element={<Energy />} />
            <Route path="/weather" element={<Weather />} />
            <Route path="/planning" element={<Planning />} />
          </Route>
        </Routes>
      </PlannerProvider>
    </BrowserRouter>
  )
}
