import type { NodeOptions } from "@sentry/nextjs";

// Sentry's v11 SDK collects cookies, headers, bodies, query strings and variables from stack frames
// unless told not to (v10 collected none of them). For this app those would include the session cookie
// and what students typed, so everything is switched off: an error report says where it happened and
// what it was, nothing else.
export const privateDataCollection: NonNullable<NodeOptions["dataCollection"]> = {
  userInfo: false,
  cookies: false,
  httpHeaders: { request: false, response: false },
  httpBodies: [],
  urlQueryParams: false,
  genAI: { inputs: false, outputs: false },
  databaseQueryData: false,
  queues: false,
  stackFrameVariables: false,
};
