import { createApp } from "vue";

import { uiPlugin } from "@hiwindows/ui";
import App from "./App.vue";
import router from "./router";
import "@hiwindows/ui/styles.css";
import "./style.css";

createApp(App).use(router).use(uiPlugin).mount("#app");
