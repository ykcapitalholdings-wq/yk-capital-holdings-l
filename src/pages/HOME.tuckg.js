import wixLocation from 'wix-location';

$w.onReady(() => {
  const waNumber = "905360340313";
  const msg = encodeURIComponent(
    "EN: Hi Y&K Capital Holdings — I’d like a shipping quote (US↔TR). " +
    "Pickup city/state: __, Delivery city: __, Weight (kg): __, Volume (CBM): __, Incoterm: __, Ready date: __.\n\n" +
    "TR: Merhaba Y&K Capital — ABD↔TR sevkiyat için teklif almak istiyorum. " +
    "Alım şehri: __, Teslim şehri: __, Ağırlık (kg): __, Hacim (CBM): __, Incoterm: __, Hazır tarihi: __."
  );

  const waLink = `https://wa.me/${waNumber}?text=${msg}`;

  $w("#whatsBtn").onClick(() => {
    wixLocation.to(waLink);
  });
});
