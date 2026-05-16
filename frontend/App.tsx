import React from 'react'
import { Routes, Route } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import Layout from './components/Layout'
import { AuthGuard, GuestGuard } from './components/AuthGuard'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import TaskList from './pages/TaskList'
import AnnotationWorkspace from './pages/AnnotationWorkspace'
import ImageAnnotation from './pages/ImageAnnotation'
import PointCloudAnnotation from './pages/PointCloudAnnotation'
import EmbodiedAnnotation from './pages/EmbodiedAnnotation'
import TextAnnotation from './pages/TextAnnotation'
import AudioAnnotation from './pages/AudioAnnotation'
import VideoAnnotation from './pages/VideoAnnotation'
import MultimodalAnnotation from './pages/MultimodalAnnotation'
import Projects from './pages/Projects'
import { useTheme } from './contexts/ThemeContext'
import './index.css'

function App() {
  const { isDark } = useTheme()

  return (
    <>
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: isDark ? '#12121a' : '#ffffff',
            color: isDark ? '#e2e8f0' : '#1e293b',
            border: `1px solid ${isDark ? '#1e1e2e' : '#e2e8f0'}`,
          },
        }}
      />
      <Routes>
        {/* 公开路由 */}
        <Route path="/login" element={
          <GuestGuard>
            <Login />
          </GuestGuard>
        } />
        <Route path="/register" element={
          <GuestGuard>
            <Register />
          </GuestGuard>
        } />

        {/* 受保护路由 */}
        <Route path="/" element={
          <AuthGuard>
            <Layout />
          </AuthGuard>
        }>
          <Route index element={<Dashboard />} />
          <Route path="projects" element={<Projects />} />
          <Route path="tasks" element={<TaskList />} />
          <Route path="annotate-embodied/:taskId" element={<EmbodiedAnnotation />} />
          <Route path="annotate-3d/:taskId" element={<PointCloudAnnotation />} />
          <Route path="annotate-image/:taskId" element={<ImageAnnotation />} />
          <Route path="annotate-text/:taskId" element={<TextAnnotation />} />
          <Route path="annotate-audio/:taskId" element={<AudioAnnotation />} />
          <Route path="annotate-video/:taskId" element={<VideoAnnotation />} />
          <Route path="annotate-multimodal/:taskId" element={<MultimodalAnnotation />} />
          <Route path="annotate/:taskId" element={<AnnotationWorkspace />} />
        </Route>
      </Routes>
    </>
  )
}

export default App
