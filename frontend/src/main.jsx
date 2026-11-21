import { lazy, StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router";
import "./index.css";
import Layout from "./components/Layout";
import { PageLoader } from "./components/ui";
import { AuthProvider, useAuth } from "./lib/auth";
import { ThemeProvider } from "./lib/theme";
import Browse from "./pages/Browse";
import Home from "./pages/Home";
import NotFound from "./pages/NotFound";

// Less-visited pages are loaded on demand, so the first page load stays small
// (the chart library, for example, is only downloaded on product pages).
const Admin = lazy(() => import("./pages/Admin"));
const Assistant = lazy(() => import("./pages/Assistant"));
const Builder = lazy(() => import("./pages/Builder"));
const ListingForm = lazy(() => import("./pages/ListingForm"));
const ListingPage = lazy(() => import("./pages/ListingPage"));
const Login = lazy(() => import("./pages/Auth").then((m) => ({ default: m.Login })));
const Register = lazy(() => import("./pages/Auth").then((m) => ({ default: m.Register })));
const Marketplace = lazy(() => import("./pages/Marketplace"));
const Notifications = lazy(() => import("./pages/Notifications"));
const ProductPage = lazy(() => import("./pages/ProductPage"));
const Profile = lazy(() => import("./pages/Profile"));
const Settings = lazy(() => import("./pages/Settings"));
const Wishlist = lazy(() => import("./pages/Wishlist"));

// Pages that need a logged-in user redirect to /login and come back afterwards.
function RequireAuth({ children, admin = false }) {
  const { user, ready } = useAuth();
  const location = useLocation();
  if (!ready) return <PageLoader />;
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`} replace />;
  if (admin && !user.is_admin) return <Navigate to="/" replace />;
  return children;
}

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <ThemeProvider>
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Home />} />
            <Route path="parts/:category" element={<Browse />} />
            <Route path="search" element={<Browse />} />
            <Route path="product/:id" element={<ProductPage />} />
            <Route path="builder" element={<Builder />} />
            <Route path="assistant" element={<Assistant />} />
            <Route path="marketplace" element={<Marketplace />} />
            <Route path="marketplace/new" element={<RequireAuth><ListingForm /></RequireAuth>} />
            <Route path="marketplace/:id" element={<ListingPage />} />
            <Route path="marketplace/:id/edit" element={<RequireAuth><ListingForm /></RequireAuth>} />
            <Route path="u/:username" element={<Profile />} />
            <Route path="wishlist" element={<RequireAuth><Wishlist /></RequireAuth>} />
            <Route path="notifications" element={<RequireAuth><Notifications /></RequireAuth>} />
            <Route path="settings" element={<RequireAuth><Settings /></RequireAuth>} />
            <Route path="admin" element={<RequireAuth admin><Admin /></RequireAuth>} />
            <Route path="login" element={<Login />} />
            <Route path="register" element={<Register />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
    </ThemeProvider>
  </StrictMode>,
);
