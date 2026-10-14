export default function HopTracker({events}) {
    const hopEvents = events.filter((event) => event.type === 'HOP_COMPLETED');
    return (
        <div className="border p-4 rounded-xl">
            <h2>HopTracker</h2>
            {hopEvents.map((event, index) => (
                <div key={index}>
                    Hop {event.hop_count} {' -> '} {event.route.join(' -> ')}
                </div>
            ))}
        </div>
    );
}