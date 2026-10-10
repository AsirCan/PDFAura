import "./app.css";
import { mount } from "svelte";
import App from "./App.svelte";
import { keepLinksOutside } from "./lib/links";

keepLinksOutside();

mount(App, { target: document.getElementById("app")! });
