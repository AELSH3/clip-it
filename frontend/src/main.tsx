import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout.tsx";
import { CollectionsPage } from "./pages/CollectionsPage.tsx";
import { EvaluationPage } from "./pages/EvaluationPage.tsx";
import { LibraryPage } from "./pages/LibraryPage.tsx";
import { SearchPage } from "./pages/SearchPage.tsx";
import { WatchPage } from "./pages/WatchPage.tsx";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<LibraryPage />} />
          <Route path="search" element={<SearchPage />} />
          <Route path="videos/:id" element={<WatchPage />} />
          <Route path="collections" element={<CollectionsPage />} />
          <Route path="evaluation" element={<EvaluationPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);
