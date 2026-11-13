// Entry point: fonts and global styles, the remembered theme, the login key
// out of the URL, then the app.
import "@fontsource/ibm-plex-mono/latin-400.css";
import "@fontsource/ibm-plex-mono/latin-400-italic.css";
import "@fontsource/ibm-plex-mono/latin-600.css";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/motion.css";
import { createRoot } from "react-dom/client";
import { App } from "./app";
import { loadTheme, setTheme, takeHashLink } from "./state";

setTheme(loadTheme());
// Take the one-shot key (and the view to open on) and drop the fragment before anything renders.
const link = takeHashLink();

const root = document.getElementById("root");
if (!root) throw new Error("index.html has no #root");
// No StrictMode: its doubled effects would spend the one-shot login key twice.
createRoot(root).render(<App link={link} />);
