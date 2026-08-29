export type Locale = "en" | "hi";

export type Destination = "today" | "circle" | "mentors";

export type Session = {
  uid: string;
  displayName: string;
  roles: string[];
  synthetic: boolean;
};

export interface AuthGateway {
  sendEmailLink(email: string): Promise<void>;
  signInWithGoogle(): Promise<Session>;
  createDemoSession(): Promise<Session>;
}
