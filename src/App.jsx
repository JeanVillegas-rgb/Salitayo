import { createBrowserRouter, RouterProvider } from "react-router-dom";
import SignUp           from "./pages/SignUp";
import Login            from "./pages/Login";
import VerifyEmail      from "./pages/VerifyEmail";
import Landing          from "./pages/Landing";
import Home             from "./pages/Home";
import WritingAssistant from "./pages/WritingAssistant";
import WordProficiency  from "./pages/WordProficiency";  
import ProtectedRoute   from "./components/ProtectedRoute";
import "./styles/global.css";

const router = createBrowserRouter([
  { path: "/",                    element: <Landing /> },
  { path: "/signup",              element: <SignUp /> },
  { path: "/login",               element: <Login /> },
  { path: "/verify-email/:token", element: <VerifyEmail /> },
  { path: "/verify-email/resend", element: <VerifyEmail /> },
  {
    path: "/home",
    element: <ProtectedRoute><Home /></ProtectedRoute>,
  },
  {
    path: "/writing",
    element: <ProtectedRoute><WritingAssistant /></ProtectedRoute>,
  },
  {
    path: "/wordproficiency",
    element: <ProtectedRoute><WordProficiency /></ProtectedRoute>,
  },
]);

function App() {
  return <RouterProvider router={router} />;
}

export default App;