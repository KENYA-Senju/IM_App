//EXPAND THE SAME ITEM FUNCTIONALITY TO PROJECT BASED FILTERING AS WELL 
const filterRadios = document.querySelectorAll('input[name="filter"]');
const orderOptions = document.getElementById('orderOptions');
const itemOptions = document.getElementById('itemOptions');
const itemSearch = document.getElementById("itemSearch")
const itemTypeRadios = document.querySelectorAll('input[name="itemType"]');
const HEADINGS = ["ID", "MATERIAL_ID", "OPERATION", "QUANTITY", "TIMESTAMP", "PROJECT", "BEFORE", "CHANGE"]
const l = document.getElementById("infographic");
const goButton = document.getElementById("go")

 // Show item options when "Item" is selected
filterRadios.forEach(radio => {
    radio.addEventListener('change', () => {
    if (radio.value === "Material" || radio.value === "Project") {
        itemOptions.classList.remove('hidden');
        itemSearch.classList.add('hidden'); 
        orderOptions.classList.add('hidden');
    } else if (radio.value ==="Recent" ){ 
        orderOptions.classList.remove('hidden')
        itemOptions.classList.add('hidden');
        itemSearch.classList.add('hidden');
    }else {
        itemOptions.classList.add('hidden');
        itemSearch.classList.add('hidden'); // hide search if leaving item
        orderOptions.classList.add('hidden');
        }
    });
});

// Show search box when "Specific Item" is selected
itemTypeRadios.forEach(radio => {
    radio.addEventListener('change', () => {
        if (radio.value === "Specific") {
            itemSearch.classList.remove('hidden');
        } else {
            itemSearch.classList.add('hidden');
        }
    });
});



const API = window.API_BASE || "http://localhost:8000";
async function applyRequest(DICT, endpoint = "/IM-server") {
    console.log("Sending Data to Server:", DICT);
    const response = await fetch(`${API}${endpoint}`, {
        method: 'POST',
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(DICT)
    });
    const data = await response.json();
    return data;
}

function addHeaders(){ 
    const a = document.createElement("tr")
    // add headings to program 
    HEADINGS.forEach((element) => { 
        const b = document.createElement("th") 
        b.textContent  = element
        a.appendChild(b)
    });
    l.appendChild(a) 
}



// updating the log 
goButton.addEventListener("click", async function () {
    await ensureConnected();
    const currentFilter = document.querySelector('input[name="filter"]:checked')?.value;
    /* For Each case, send a unique HTTP request with another fetch function*/ 
    let log = null; // be carefull about this 
    switch(currentFilter){ 
        case "Material": 
            console.log("1.Filtering by Material")
            const materialType = document.querySelector('input[name="itemType"]:checked')?.value;
            switch(materialType){ 
                case "All":
                    console.log("2. Grouping All Items")
                    log = await applyRequest({code:"f", aspect: "Material"}, "/IM-server")
                    break;
                case "Specific": 
                    console.log("2. Grouping Only The Specified Material")
                    const search = document.getElementById("log_search").value;
                    
                    log = await applyRequest({code:"g", object:search, aspect: "Material"}, "/IM-server")
                    break; 
                default: 
                    console.log("2. No Material Type Selected") 

            }
            break;
                case "Recent": 
                    console.log("1. Sorting by TimeStamp") 
                    const listing = document.querySelector('input[name="order"]:checked')?.value;
                    switch(listing){
                        case "Ascending": 
                            console.log("2. Sorting In Ascending Order") 
                            log =await  applyRequest({code:"d", key:1}, "/IM-server")
                            break;
                        case "Descending": 
                            console.log("2. Sorting In Descending Order") 
                            log =await  applyRequest({code:"d", key:-1}, "/IM-server")
                            break;
                        case "Arbitrary": 
                            console.log("2. Sorting At Random") 
                            log =await  applyRequest({code:"e"}, "/IM-server")
                            break;
                        default: 
                            console.log("2. No Sorting Order Selected")
                            
                    }
            break;

        case "Project":
            console.log("1.Filtering by Project");
            const projectType = document.querySelector('input[name="itemType"]:checked')?.value;

            switch (projectType) {
                case "All":
                    log = await applyRequest(
                            { code: "f", aspect: "Project" },
                            "/IM-server"
                    );
                    break;

                case "Specific":
                    const projectSearch = document.getElementById("log_search").value;
                    log = await applyRequest(
                            { code: "g", object: projectSearch, aspect: "Project" },
                            "/IM-server"
                    );
                    break;

                default:
                    console.log("2. No Project Type Selected");
                }
            break;
        
        default: 
            console.log("1. No Filter Selected")
        
    }
    /* Any responses that are not none (log !== null) will be displayed on the websiste just under the Go Button */
    
    if (log !== null){ 
        l.innerHTML = "";
        console.log("Displaying Logged Data")
        transactions = log["log"]
        console.log("Displaying Transaction History") 
        console.log(transactions)
        console.log("Displaying Individual Elements") 
        addHeaders()
        for(let i = 0; i< transactions.length;i++){ 
            // add entire row to table 
            const a = document.createElement("tr") 
           
            for (const value of Object.values(transactions[i])) {
                const b = document.createElement("th");
                console.log(value)
                b.textContent = value;
                a.appendChild(b);    
            }
            // the entire row has been complete, add to the table 
            l.appendChild(a);
        }
        console.log("Finished Display")
    }
});