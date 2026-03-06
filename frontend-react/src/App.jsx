import React from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./context/AuthContext.jsx";
import DashboardLayout from "./components/DashboardLayout.jsx";
import ProtectedRoute from "./components/ProtectedRoute.jsx";
import AdminDashboard from "./pages/AdminDashboard.jsx";
import AdminDatabasePage from "./pages/AdminDatabasePage.jsx";
import AdminReportsPage from "./pages/AdminReportsPage.jsx";
import AdminUsersPage from "./pages/AdminUsersPage.jsx";
import CustomerDashboard from "./pages/CustomerDashboard.jsx";
import ForbiddenPage from "./pages/ForbiddenPage.jsx";
import HomePage from "./pages/HomePage.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import NotFoundPage from "./pages/NotFoundPage.jsx";
import ProducerDashboard from "./pages/ProducerDashboard.jsx";
import ProducerOrdersPage from "./pages/ProducerOrdersPage.jsx";
import ProducerPaymentsPage from "./pages/ProducerPaymentsPage.jsx";
import ProducerProductsPage from "./pages/ProducerProductsPage.jsx";
import UnauthorizedPage from "./pages/UnauthorizedPage.jsx";
import ProductListPage from "./pages/ProductListPage.jsx";
import ProductDetailPage from "./pages/ProductDetailPage.jsx";
import CartPage from "./pages/CartPage.jsx";
import CheckoutPage from "./pages/CheckoutPage.jsx";

function HomeRedirect() {
  const { user } = useAuth();
  if (!user) return <HomePage />;
  if (user.role === "producer") return <Navigate to="/producer" replace />;
  if (user.role === "admin") return <Navigate to="/admin" replace />;
  return <Navigate to="/customer" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomeRedirect />} />
      <Route path="/products" element={<ProductListPage />} />
      <Route path="/products/:id" element={<ProductDetailPage />} />
      <Route path="/cart" element={<CartPage />} />
      <Route path="/checkout" element={<CheckoutPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/401" element={<UnauthorizedPage />} />
      <Route path="/403" element={<ForbiddenPage />} />

      <Route
        path="/producer"
        element={
          <ProtectedRoute allowedRoles={["producer"]}>
            <DashboardLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<ProducerDashboard />} />
        <Route path="products" element={<ProducerProductsPage />} />
        <Route path="orders" element={<ProducerOrdersPage />} />
        <Route path="payments" element={<ProducerPaymentsPage />} />
      </Route>

      <Route
        path="/admin"
        element={
          <ProtectedRoute allowedRoles={["admin"]}>
            <DashboardLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<AdminDashboard />} />
        <Route path="reports" element={<AdminReportsPage />} />
        <Route path="users" element={<AdminUsersPage />} />
        <Route path="database" element={<AdminDatabasePage />} />
      </Route>

      <Route
        path="/customer"
        element={
          <ProtectedRoute allowedRoles={["customer"]}>
            <DashboardLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<CustomerDashboard />} />
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
