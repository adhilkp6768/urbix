"use client";

import { AppFrame } from "@/components/mobile/AppFrame";

export default function MobileLayout({ children }: { children: React.ReactNode }) {
  return <AppFrame>{children}</AppFrame>;
}
