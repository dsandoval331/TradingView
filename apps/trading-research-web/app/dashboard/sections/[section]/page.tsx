import {notFound} from "next/navigation";
import DashboardContent from "../../DashboardContent";
import {DOMAIN_SECTIONS} from "../../DomainNavigation";
export const dynamic="force-dynamic";
export default async function SectionPage({params}:{params:Promise<{section:string}>}){
 const {section}=await params;
 if(!DOMAIN_SECTIONS.some(item=>item.id===section&&item.id!=="osi-analysis"))notFound();
 return <DashboardContent section={section}/>;
}
