import React from "react";
import ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { SWRConfig } from "swr";
import { fetcher } from "./api";
import App from "./App";
import Overview from "./pages/Overview";
import Alerts from "./pages/Alerts";
import Wallets from "./pages/Wallets";
import WalletDetail from "./pages/WalletDetail";
import Performance from "./pages/Performance";
import System from "./pages/System";
import "./index.css";

const router = createBrowserRouter([{
  path: "/",
  element: <App />,
  children: [
    { index: true, element: <Overview /> },
    { path: "alerts", element: <Alerts /> },
    { path: "wallets", element: <Wallets /> },
    { path: "wallets/:address", element: <WalletDetail /> },
    { path: "performance", element: <Performance /> },
    { path: "system", element: <System /> },
  ],
}]);

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <SWRConfig value={{
      fetcher,
      revalidateOnFocus: true,
      dedupingInterval: 5000,
      errorRetryCount: 2,
      errorRetryInterval: 5000,
    }}>
      <RouterProvider router={router} />
    </SWRConfig>
  </React.StrictMode>
);
