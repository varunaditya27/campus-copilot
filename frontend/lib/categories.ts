import type { EventCategory } from "./types";

// The event categories, in the order they are shown, with their display names.
export const EVENT_CATEGORIES: { value: EventCategory; label: string }[] = [
  { value: "artificial-intelligence", label: "Artificial intelligence" },
  { value: "web-development", label: "Web development" },
  { value: "competitive-programming", label: "Competitive programming" },
  { value: "cybersecurity", label: "Cybersecurity" },
  { value: "research", label: "Research" },
  { value: "robotics", label: "Robotics" },
];
