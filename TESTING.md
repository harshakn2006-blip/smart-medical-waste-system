# Manual testing checklist

Run the app locally, then verify the following.

| Test | Steps | Expected result |
|---|---|---|
| Login success | Sign in as `staff` / `Staff123!` | Dashboard opens |
| Login failure | Use an incorrect password | Error message appears |
| Role restriction | Sign in as `collector`, then manually visit `/waste` | Access denied (403) |
| Known phrase | Segregation guide: `contaminated IV tubing` | Red suggestion with verification note |
| Sharps phrase | Segregation guide: `needle` | White (translucent) suggestion |
| Unknown item | Segregation guide: `mystery chemical pack` | Needs trained staff review |
| Add record | Staff adds item, department and positive quantity | Record appears in register and dashboard |
| Invalid quantity | Enter zero or negative quantity | Record is not saved |
| Create pickup | Submit collection request | Request appears with Pending status |
| Assign pickup | Admin assigns a collector and sets Assigned | Request shows assigned collector |
| Collector update | Assigned collector marks Collected, then Completed | Status updates are saved |
| Create account | Admin creates a new user with valid role/password | New account appears in user list |
| Mobile layout | Resize browser to phone width | Navigation and forms remain usable |

For any real clinical or operational use, perform a formal security, usability, regulatory, and workflow validation with the healthcare facility.
