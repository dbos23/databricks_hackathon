import { createApp, analytics, genie, server } from "@databricks/appkit";

await createApp({
  plugins: [
    analytics(),
    server(),
    genie({
      spaces: {
        default: process.env.DATABRICKS_GENIE_SPACE_ID!,
      },
    }),
  ],
});