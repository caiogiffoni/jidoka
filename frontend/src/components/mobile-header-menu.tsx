"use client";

import { Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";

export interface MobileHeaderMenuItem {
  id: string;
  label: string;
  node: React.ReactNode;
  closeOnClick?: boolean;
}

function MenuRow({ item }: { item: MobileHeaderMenuItem }) {
  const row = (
    <div className="flex items-center gap-3 rounded-lg px-2 py-2 hover:bg-muted/50">
      {item.node}
      <span className="text-sm">{item.label}</span>
    </div>
  );

  if (item.closeOnClick) {
    return <SheetClose asChild>{row}</SheetClose>;
  }
  return row;
}

export function MobileHeaderMenu({ items }: { items: MobileHeaderMenuItem[] }) {
  return (
    <div className="flex sm:hidden">
      <Sheet>
        <SheetTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Open menu"
            className="shrink-0"
          >
            <Menu className="size-5" />
          </Button>
        </SheetTrigger>
        <SheetContent side="right" className="w-64">
          <SheetHeader>
            <SheetTitle>Menu</SheetTitle>
          </SheetHeader>
          <nav className="mt-4 flex flex-col gap-1">
            {items.map((item) => (
              <MenuRow key={item.id} item={item} />
            ))}
          </nav>
        </SheetContent>
      </Sheet>
    </div>
  );
}
