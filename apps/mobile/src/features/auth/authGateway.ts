import type { AuthGateway, Session } from "./types";

export class AuthNotConfiguredError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AuthNotConfiguredError";
  }
}

const demoSession: Session = {
  uid: "demo-meera",
  displayName: "Meera",
  roles: ["learner"],
  synthetic: true,
};

export const unconfiguredAuthGateway: AuthGateway = {
  async sendEmailLink() {
    throw new AuthNotConfiguredError("Email sign-in is not configured yet.");
  },
  async signInWithGoogle() {
    throw new AuthNotConfiguredError("Google sign-in is not configured yet.");
  },
  async createDemoSession() {
    return demoSession;
  },
};
