import { useState } from 'react';

export function TrackFilter({ setColumnFilters }) {
    const [filterOption, setFilterOption] = useState('all');
    const [fromTrack, setFromTrack] = useState('');
    const [toTrack, setToTrack] = useState('');
    const applyFilter = () => {
        if (filterOption === 'range' && fromTrack && toTrack) {
          setColumnFilters([
            { id: 'track', value: { from: parseInt(fromTrack, 10), to: parseInt(toTrack, 10) } }
          ]);
        } else {
          setColumnFilters([]); // Clear filters when "All Tracks" is selected
        }
      };
      
    

    return (
        <div>
            <div>
                <input
                    type="radio"
                    name="trackFilter"
                    value="all"
                    checked={filterOption === 'all'}
                    onChange={() => setFilterOption('all')}
                /> All Tracks
                <input
                    type="radio"
                    name="trackFilter"
                    value="range"
                    checked={filterOption === 'range'}
                    onChange={() => setFilterOption('range')}
                /> Range:
                {filterOption === 'range' && (
                    <>
                        <input
                            type="number"
                            placeholder="From Track"
                            value={fromTrack}
                            onChange={e => setFromTrack(e.target.value)}
                        />
                        <input
                            type="number"
                            placeholder="To Track"
                            value={toTrack}
                            onChange={e => setToTrack(e.target.value)}
                        />
                        <button onClick={applyFilter}>Apply</button>
                    </>
                )}
            </div>
        </div>
    );
}
