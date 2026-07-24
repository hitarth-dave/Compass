import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from "@/components/ui/accordion";

export default function FAQ({ items, title = "Questions, answered." }) {
  return (
    <section className="max-w-3xl mx-auto px-6 lg:px-12 mt-24 fade-up" data-testid="faq-section">
      <div className="text-center mb-10">
        <div className="overline mb-4">FAQ</div>
        <h2 className="font-serif-display text-3xl sm:text-4xl text-[color:var(--jai-green-deep)]">{title}</h2>
      </div>
      <Accordion type="single" collapsible className="card-surface px-6 sm:px-8">
        {items.map((item, i) => (
          <AccordionItem key={item.q} value={`item-${i}`} className="border-[color:var(--jai-border)]">
            <AccordionTrigger className="font-serif-display text-lg text-[color:var(--jai-green-deep)] hover:no-underline">
              {item.q}
            </AccordionTrigger>
            <AccordionContent className="text-sm text-[color:var(--jai-text-muted)] leading-relaxed">
              {item.a}
            </AccordionContent>
          </AccordionItem>
        ))}
      </Accordion>
    </section>
  );
}
